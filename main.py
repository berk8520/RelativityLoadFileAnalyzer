import flet as ft
import os
import asyncio
import gc
import tkinter as tk
import polars as pl
from tkinter import filedialog

# Real processor functions
from processor import analyze_load_file, load_mapping_csv, normalize_field_name, remap_headers, find_sequence_gaps

class RelativityLoadFileAnalyzer:
    def __init__(self, page: ft.Page):
        self.page = page
        self.selected_file_path = None
        self.cross_ref_path = None
        self.analysis_results = []
        self.rename_map = {}
        self.filters = {} # Store current filter values
        self.max_operator = "=" # Store selected operator for Max Length numeric filter
        self.table_lock = asyncio.Lock() # Prevent race conditions during rapid filtering

    async def initialize(self):
        self.setup_page()
        self.build_ui()
        self.page.update()

    def setup_page(self):
        import sys
        # Handle pathing for PyInstaller --onefile
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.getcwd()

        # Force the Window Icon to be the new .ico logo
        icon_path = os.path.join(base_path, "assets", "app_icon.ico")
        self.page.window_icon = icon_path
        self.page.favicon = "pageone-logo.png"
        
        try:
            self.page.window.icon = icon_path
        except:
            pass
            
        self.page.debug_show_checked_mode_banner = False
        self.page.title = "Relativity Load File Analyzer"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.padding = 20
        self.page.window_width = 1200
        self.page.window_height = 850
        self.page.theme = ft.Theme(
            color_scheme_seed=ft.Colors.BLUE_ACCENT,
            visual_density=ft.VisualDensity.COMFORTABLE,
        )
        self.page.bgcolor = "#0F172A"  # Slate 900

    def build_ui(self):
        # Named Action buttons to avoid index-based layout references
        self.btn_open = ft.Button("Open File", icon=ft.Icons.FILE_OPEN_ROUNDED, on_click=self.open_file_click, height=45, style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_ACCENT_700, color=ft.Colors.WHITE))
        self.btn_load_map = ft.Button("Load Mapping", icon=ft.Icons.MAP_ROUNDED, on_click=self.load_cross_ref_click, height=45, disabled=True)
        self.btn_find_gaps = ft.Button("Find Gaps", icon=ft.Icons.FIND_IN_PAGE_ROUNDED, on_click=self.find_gaps_click, height=45, disabled=True, style=ft.ButtonStyle(bgcolor=ft.Colors.ORANGE_800, color=ft.Colors.WHITE))
        self.btn_export_analysis = ft.Button("Export Analysis", icon=ft.Icons.DOWNLOAD_ROUNDED, on_click=self.export_analysis_click, height=45, disabled=True)
        self.btn_export_remapped = ft.Button("Export Remapped", icon=ft.Icons.SAVE_ALT_ROUNDED, on_click=self.export_click, height=45, disabled=True, style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_800, color=ft.Colors.WHITE))

        self.btn_help = ft.IconButton(
            icon=ft.Icons.HELP_OUTLINE_ROUNDED,
            tooltip="Show Help & Instructions",
            on_click=self.show_help_click,
            icon_color=ft.Colors.BLUE_GREY_100,
        )

        self.progress_ring = ft.ProgressRing(visible=False, width=20, height=20, stroke_width=3, color=ft.Colors.BLUE_ACCENT)
        
        # Header Section with auto-wrapping to prevent elements pushing off-screen
        self.header = ft.Row(
            [
                ft.Row(
                    [
                        ft.Container(
                            content=ft.Image(src="pageone-logo.png", height=40, fit="contain"),
                            bgcolor=ft.Colors.WHITE,
                            padding=ft.Padding(5, 5, 5, 5),
                            border_radius=5,
                        ),
                        ft.Column(
                            [
                                ft.Text("Relativity Load File Analyzer", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                ft.Text("E-Discovery Schema Utility", size=11, color=ft.Colors.BLUE_GREY_400),
                            ],
                            spacing=0,
                        ),
                    ],
                    spacing=15,
                ),
                # Action Ribbon with inline Help button
                ft.Row(
                    [
                        self.btn_open,
                        self.btn_load_map,
                        self.btn_find_gaps,
                        self.btn_export_analysis,
                        self.btn_export_remapped,
                        self.btn_help,
                    ],
                    spacing=10,
                ),
                ft.Row(
                    [
                        self.progress_ring,
                    ],
                    spacing=5,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            wrap=True,
        )

        # Status Cards (Config Bar) with auto-wrapping to prevent off-screen overflow
        self.encoding_card = self.create_status_card("Encoding", "Not Detected", ft.Icons.CODE_ROUNDED, width=220)
        self.row_count_card = self.create_status_card("Row Count", "0", ft.Icons.TABLE_ROWS_ROUNDED, width=180)
        self.col_count_card = self.create_status_card("Col Count", "0", ft.Icons.VIEW_COLUMN_ROUNDED, width=180)
        self.delimiter_card = self.create_status_card("Delimiter", "Not Detected", ft.Icons.STAIRS_ROUNDED, width=450)

        self.config_bar = ft.Row(
            [self.encoding_card, self.row_count_card, self.col_count_card, self.delimiter_card],
            spacing=10,
            alignment=ft.MainAxisAlignment.START,
            wrap=True,
        )

        # Filter Row
        self.filter_row = ft.Row(spacing=40)
        
        # Results Table (Rows only)
        self.results_table = ft.DataTable(
            bgcolor="#1E293B",
            border=ft.Border.all(1, "#334155"),
            border_radius=ft.BorderRadius(top_left=0, top_right=0, bottom_left=10, bottom_right=10),
            vertical_lines=ft.BorderSide(1, "#334155"),
            column_spacing=40,
            heading_row_height=0, # Hide the built-in header
            columns=[
                ft.DataColumn(ft.Container(width=200)),
                ft.DataColumn(ft.Container(width=180)),
                ft.DataColumn(ft.Container(width=80)),
                ft.DataColumn(ft.Container(width=650)),
            ],
            rows=[],
        )

        # Fixed Header Bar
        self.header_row_control = ft.Row(
            [
                ft.Container(ft.Text("Original Name", weight=ft.FontWeight.BOLD), width=200, padding=10),
                ft.Container(ft.Text("Relativity Field Type", weight=ft.FontWeight.BOLD), width=180, padding=10),
                ft.Container(ft.Text("Max Len", weight=ft.FontWeight.BOLD), width=80, padding=10),
                ft.Container(ft.Text("Longest Value Example", weight=ft.FontWeight.BOLD), width=650, padding=10),
            ],
            spacing=40,
        )

        # Gap Report UI Controls
        self.gap_results_table = ft.DataTable(
            bgcolor="#1E293B",
            border=ft.Border.all(1, "#334155"),
            border_radius=ft.BorderRadius(10, 10, 10, 10),
            vertical_lines=ft.BorderSide(1, "#334155"),
            column_spacing=40,
            columns=[
                ft.DataColumn(ft.Text("Prefix", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Gap Start", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Gap End", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Missing Count", weight=ft.FontWeight.BOLD)),
            ],
            rows=[],
        )
        self.gap_results = []
        
        self.gap_export_button = ft.Button(
            "Export Gap Report CSV",
            icon=ft.Icons.DOWNLOAD_ROUNDED,
            on_click=self.export_gap_report_click,
            disabled=True,
            style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_ACCENT_700, color=ft.Colors.WHITE)
        )

        # Schema Analysis Content
        self.schema_tab_content = ft.Column(
            [
                ft.Row([
                    ft.Text("Schema Analysis Results", size=18, weight=ft.FontWeight.W_600),
                    ft.VerticalDivider(),
                    ft.Text("(Use boxes below to filter columns)", size=12, color=ft.Colors.BLUE_GREY_400),
                ]),
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Column(
                                [
                                    # Filters (move horizontally with columns)
                                    ft.Container(self.filter_row, padding=ft.Padding(left=10, top=10, right=0, bottom=10)),
                                    # Fixed Header Bar Container
                                    ft.Container(
                                        content=self.header_row_control,
                                        bgcolor="#0F172A",
                                        border=ft.Border.all(1, "#334155"),
                                        border_radius=ft.BorderRadius(top_left=10, top_right=10, bottom_left=0, bottom_right=0),
                                    ),
                                    # Vertically Scrollable Data Area
                                    ft.Column(
                                        [self.results_table],
                                        scroll=ft.ScrollMode.ADAPTIVE,
                                        expand=True,
                                    )
                                ],
                                expand=True,
                                spacing=0,
                            )
                        ],
                        scroll=ft.ScrollMode.ADAPTIVE,
                        expand=True,
                    ),
                    border_radius=10,
                    expand=True,
                ),
            ],
            expand=True,
        )

        # Gap Report Content
        self.gap_tab_content = ft.Column(
            [
                ft.Row([
                    ft.Text("Gap Analysis Results", size=18, weight=ft.FontWeight.W_600),
                    ft.VerticalDivider(),
                    self.gap_export_button
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Container(
                    content=ft.Column(
                        [
                            self.gap_results_table
                        ],
                        scroll=ft.ScrollMode.ADAPTIVE,
                        expand=True,
                    ),
                    border_radius=10,
                    expand=True,
                )
            ],
            expand=True,
        )

        # Set up Tabs view
        # Tabs requires explicit nested structure in this Flet version
        self.tab_bar = ft.TabBar(
            tabs=[
                ft.Tab(label="Schema Analysis"),
                ft.Tab(label="Gap Report"),
            ],
            on_click=self.on_tab_change
        )
        self.tab_bar_view = ft.TabBarView(
            expand=True,
            controls=[
                self.schema_tab_content,
                self.gap_tab_content,
            ]
        )
        self.tab_container = ft.Tabs(
            length=2,
            selected_index=0,
            animation_duration=300,
            content=ft.Column(
                expand=True,
                controls=[
                    self.tab_bar,
                    self.tab_bar_view
                ]
            ),
            expand=True,
        )

        # Footer Actions
        self.footer = ft.Row(
            [
                ft.Button(
                    "Export Analysis CSV",
                    icon=ft.Icons.DOWNLOAD_ROUNDED,
                    on_click=self.export_analysis_click,
                    disabled=True,
                    style=ft.ButtonStyle(color=ft.Colors.BLUE_ACCENT_100),
                ),
                ft.Button(
                    "Load Cross-Ref",
                    icon=ft.Icons.MAP_ROUNDED,
                    on_click=self.load_cross_ref_click,
                    disabled=True,
                ),
                ft.Button(
                    "Export Final Load File",
                    icon=ft.Icons.SAVE_ALT_ROUNDED,
                    on_click=self.export_click,
                    style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_800, color=ft.Colors.WHITE),
                    disabled=True,
                ),
            ],
            alignment=ft.MainAxisAlignment.END,
            spacing=20,
        )

        # Prominent Loading Overlay
        self.loading_text = ft.Text("Processing... Please wait", size=16, weight=ft.FontWeight.W_600, color=ft.Colors.WHITE)
        self.loading_overlay = ft.Container(
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.ProgressRing(width=60, height=60, stroke_width=5, color=ft.Colors.BLUE_ACCENT),
                        ft.Container(height=20),
                        self.loading_text,
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                width=300,
                height=180,
                bgcolor="#1E293B",
                border=ft.Border.all(2, ft.Colors.BLUE_ACCENT_700),
                border_radius=15,
                padding=20,
            ),
            alignment=ft.Alignment(0, 0),
            bgcolor="#AA000000",  # Semi-transparent backdrop
            expand=True,
            visible=False,
        )
        self.page.overlay.append(self.loading_overlay)

        # Main Layout Assembly
        self.main_container = ft.Container(
            content=ft.Column(
                [
                    self.header,
                    ft.Divider(height=40, color="#334155"),
                    self.config_bar,
                    ft.Container(height=20),
                    self.tab_container,
                ],
                expand=True,
            ),
            padding=10,
            expand=True,
            border=None,
        )
        self.page.add(self.main_container)

    def create_status_card(self, title, value, icon, width=220):
        return ft.Card(
            content=ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(icon, color=ft.Colors.BLUE_ACCENT_200, size=20),
                        ft.Text(f"{title}:", size=12, color=ft.Colors.BLUE_GREY_400),
                        ft.Text(value, size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                    ],
                    spacing=10,
                    alignment=ft.MainAxisAlignment.START,
                ),
                width=width,
                height=50,
                padding=ft.Padding(left=15, top=0, right=15, bottom=0),
                bgcolor="#1E293B", # Slate 800
                border_radius=8,
            )
        )

    def pick_file_sync(self, title, filetypes, save=False):
        # Create a temporary root for each call to ensure thread-local Tcl/Tk
        try:
            root = tk.Tk()
            root.withdraw()
            root.wm_attributes('-topmost', 1)
            if save:
                path = filedialog.asksaveasfilename(title=title, filetypes=filetypes, defaultextension=".dat")
            else:
                path = filedialog.askopenfilename(title=title, filetypes=filetypes)
            root.destroy()
            return path
        except:
            return None

    def show_loading(self, text):
        self.loading_text.value = text
        self.loading_overlay.visible = True
        self.progress_ring.visible = True
        self.page.update()

    def hide_loading(self):
        self.loading_overlay.visible = False
        self.progress_ring.visible = False
        self.page.update()

    async def open_file_click(self, _):
        print("DEBUG: Open File button clicked.")
        filetypes = [("Load Files", "*.dat *.csv *.txt"), ("All Files", "*.*")]
        file_path = await asyncio.to_thread(self.pick_file_sync, "Open Load File", filetypes)
        print(f"DEBUG: File selected: {file_path}")

        if file_path:
            self.selected_file_path = file_path
            await self.update_status("Analyzing file...", ft.Colors.AMBER_400)
            await self.execute_analysis()

    async def load_cross_ref_click(self, _):
        filetypes = [("CSV Files", "*.csv")]
        file_path = await asyncio.to_thread(self.pick_file_sync, "Open Cross-Reference CSV", filetypes)

        if file_path:
            self.show_loading("Loading Cross-Reference CSV...")
            self.cross_ref_path = file_path
            try:
                self.rename_map = load_mapping_csv(self.cross_ref_path)
                
                # Dynamically add Target Name column if it's missing
                if len(self.results_table.columns) < 5:
                    self.results_table.columns.insert(1, ft.DataColumn(ft.Container(width=200)))
                    # Also update the fixed header ribbon
                    self.header_row_control.controls.insert(1, ft.Container(ft.Text("Target Name", weight=ft.FontWeight.BOLD), width=200, padding=10))
                
                # Rebuild filter row to include Target filter
                self.build_filter_controls(True)
                
                await self.refresh_table()
                self.btn_export_remapped.disabled = False # Export Remapped
                await self.update_status(f"Mapping loaded: {len(self.rename_map)} fields identified.", ft.Colors.GREEN_400)
            except Exception as ex:
                await self.update_status(f"Failed to load cross-ref: {str(ex)}", ft.Colors.RED_400)
            
            self.hide_loading()

    async def export_analysis_click(self, _):
        filetypes = [("CSV Files", "*.csv")]
        file_path = await asyncio.to_thread(self.pick_file_sync, "Export Analysis CSV", filetypes, True)
        if not file_path:
            return
            
        try:
            # Create a DataFrame from the results
            out_df = pl.DataFrame(self.analysis_results)
            # Rename columns for export
            out_df = out_df.rename({
                "column": "Source Field",
                "type": "Relativity Field Type",
                "max_len": "Max Length",
                "sample": "Sample Data"
            })
            out_df.write_csv(file_path)
            await self.update_status(f"Analysis exported to {os.path.basename(file_path)}", ft.Colors.GREEN_400)
        except Exception as ex:
            await self.update_status(f"Export failed: {str(ex)}", ft.Colors.RED_400)
        self.page.update()

    async def export_click(self, _):
        filetypes = [("Load Files", "*.dat"), ("CSV Files", "*.csv")]
        file_path = await asyncio.to_thread(self.pick_file_sync, "Export Final Load File", filetypes, True)

        if file_path:
            await self.execute_export(file_path)

    async def execute_analysis(self):
        print(f"DEBUG: Starting execute_analysis for {self.selected_file_path}")
        self.show_loading("Analyzing load file... please wait.")
        try:
            # Run the heavy Polars analysis in a background thread to keep UI responsive
            encoding, delimiter, row_count, schema_results = await asyncio.to_thread(
                analyze_load_file, self.selected_file_path
            )
            print(f"DEBUG: Analysis returned {len(schema_results)} columns and {row_count} rows.")
            self.analysis_results = schema_results
            
            # Update Cards (Now using the Row structure: Icon, Title, Value)
            self.encoding_card.content.content.controls[2].value = encoding
            self.delimiter_card.content.content.controls[2].value = delimiter
            self.row_count_card.content.content.controls[2].value = row_count
            self.col_count_card.content.content.controls[2].value = str(len(schema_results))
            
            await self.refresh_table()
            
            # Enable Buttons in Header Ribbon using named properties
            self.btn_load_map.disabled = False
            self.btn_find_gaps.disabled = False
            self.btn_export_analysis.disabled = False
            
            filename = os.path.basename(self.selected_file_path)
            await self.update_status(f"Analysis Complete: {filename}", ft.Colors.GREEN_400)
            
        except Exception as ex:
            await self.update_status(f"Error: {str(ex)}", ft.Colors.RED_400)
        
        gc.collect()
        self.hide_loading()

    async def refresh_table(self):
        async with self.table_lock:
            has_mapping = len(self.rename_map) > 0
            
            # Build/Update filters if needed
            if not self.filter_row.controls:
                self.build_filter_controls(has_mapping)

            # Apply Filters
            filtered_results = []
            # Pre-cache lowercased filters for high-speed matching
            f_src = self.filters.get("Source", "").lower()
            f_tgt = self.filters.get("Target", "").lower()
            f_typ = self.filters.get("Type", "").lower()
            f_max = self.filters.get("Max", "").lower()
            f_smp = self.filters.get("Sample", "").lower()

            for res in self.analysis_results:
                match = True
                normalized_column = normalize_field_name(res["column"])
                target = self.rename_map.get(normalized_column, res["column"])
                
                if f_src and f_src not in res["column"].lower(): match = False
                if match and has_mapping and f_tgt and f_tgt not in target.lower(): match = False
                if match and f_typ and f_typ not in res["type"].lower(): match = False
                if match and f_max:
                    val_len = res["max_len"]
                    try:
                        limit = int(f_max.strip())
                        op = self.max_operator
                        if op == "=":
                            if val_len != limit: match = False
                        elif op == ">":
                            if val_len <= limit: match = False
                        elif op == "<":
                            if val_len >= limit: match = False
                        elif op == ">=":
                            if val_len < limit: match = False
                        elif op == "<=":
                            if val_len > limit: match = False
                    except ValueError:
                        if f_max.strip() not in str(val_len): match = False
                if match and f_smp and f_smp not in res["sample"].lower(): match = False
                
                if match:
                    filtered_results.append(res)

            # High-performance limit: Render top 150 rows maximum to avoid UI lagging,
            # which is extremely common in Flet's DataTable rendering tree.
            rendered_limit = 150
            new_rows = []
            for res in filtered_results[:rendered_limit]:
                cells = [
                    ft.DataCell(ft.Container(ft.Text(res["column"], weight=ft.FontWeight.W_500), width=200)),
                ]
                
                # If mapping is active, add the Target Name cell
                if has_mapping:
                    normalized_column = normalize_field_name(res["column"])
                    target = self.rename_map.get(normalized_column, res["column"])
                    cells.append(ft.DataCell(ft.Container(ft.Text(target, color=ft.Colors.AMBER_400 if normalized_column in self.rename_map else ft.Colors.BLUE_GREY_400), width=200)))

                cells.extend([
                    ft.DataCell(ft.Container(ft.Text(res["type"], color=ft.Colors.BLUE_ACCENT_200), width=180)),
                    ft.DataCell(ft.Container(ft.Text(str(res["max_len"])), width=80)),
                    ft.DataCell(ft.Container(ft.Text(res["sample"], italic=True, color=ft.Colors.BLUE_GREY_200, size=12), width=650)),
                ])
                
                new_rows.append(ft.DataRow(cells=cells))
                
            self.results_table.rows = new_rows
            self.page.update()

    def build_filter_controls(self, has_mapping):
        self.filter_row.controls.clear()
        
        def create_filter_field(label, key, width):
            # Use page.run_task to correctly handle the async filter function from a lambda
            return ft.TextField(
                label=label,
                on_change=lambda e, k=key: self.page.run_task(self.on_filter_change, k, e.control.value),
                width=width,
                height=40,
                text_size=12,
                content_padding=10,
                border_color=ft.Colors.BLUE_GREY_700,
                focused_border_color=ft.Colors.BLUE_ACCENT,
            )

        self.filter_row.controls.append(create_filter_field("Source", "Source", 200))
        if has_mapping:
            self.filter_row.controls.append(create_filter_field("Target", "Target", 200))
        self.filter_row.controls.append(create_filter_field("Type", "Type", 180))
        
        # Max operator dropdown next to the numeric input field
        max_op_dropdown = ft.Dropdown(
            options=[
                ft.dropdown.Option("="),
                ft.dropdown.Option(">"),
                ft.dropdown.Option("<"),
                ft.dropdown.Option(">="),
                ft.dropdown.Option("<="),
            ],
            value=self.max_operator,
            width=70,
            height=40,
            text_size=12,
            content_padding=10,
            border_color=ft.Colors.BLUE_GREY_700,
            focused_border_color=ft.Colors.BLUE_ACCENT,
            on_change=lambda e: self.page.run_task(self.on_max_operator_change, e.control.value),
        )
        self.filter_row.controls.append(max_op_dropdown)
        self.filter_row.controls.append(create_filter_field("Max", "Max", 80))
        self.filter_row.controls.append(create_filter_field("Sample", "Sample", 650))

    async def on_filter_change(self, key, value):
        self.filters[key] = value
        await self.refresh_table()

    async def on_max_operator_change(self, value):
        self.max_operator = value
        await self.refresh_table()

    async def execute_export(self, output_path):
        self.show_loading("Exporting remapped load file... please wait.")
        try:
            # Run remapping in background thread
            count = await asyncio.to_thread(
                remap_headers, self.selected_file_path, self.cross_ref_path, output_path
            )
            await self.update_status(f"Success! Exported to {os.path.basename(output_path)}. {count} fields renamed.", ft.Colors.GREEN_400)
        except Exception as ex:
            await self.update_status(f"Export failed: {str(ex)}", ft.Colors.RED_400)
        
        self.hide_loading()

    def show_help_click(self, _):
        # Create a custom overlay modal for help
        self.help_overlay = ft.Container(
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Row([
                            ft.Text("Relativity Load File Analyzer - Help", size=20, weight=ft.FontWeight.BOLD),
                            ft.IconButton(ft.Icons.CLOSE, on_click=self.close_help)
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Divider(),
                        ft.Column([
                            ft.Text("Workflow Overview:", weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_ACCENT_200),
                            ft.Text("1. Load File: Click 'Open File' to select a .dat, .csv, or delimited .txt file."),
                            ft.Text("2. Analyze Schema: View field names, types, and max lengths. (Paged list for performance)"),
                            ft.Text("3. Field Types: Blank if empty. Control numbers are Fixed-length Text. Over 256 chars = 'Long Text'."),
                            ft.Text("4. Mapping: Load a Cross-Ref CSV to map source headers to targets."),
                            ft.Text("5. Find Gaps: Run sequential control number check to populate the Gap Report tab."),
                            ft.Text("6. Export: Save schema analysis, Gap Report, or final remapped load file."),
                            ft.Divider(),
                            ft.Text("Relativity Field Types:", weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_ACCENT_200),
                            ft.Text("• Whole Number / Decimal: Detected from numeric patterns."),
                            ft.Text("• Date: Detected via header hints and pattern matching."),
                            ft.Text("• Fixed-length Text: Standard text under 256 characters."),
                            ft.Text("• Long Text: Text exceeding 256 characters."),
                            ft.Text("• Empty/Blank: If max length is 0, no type is assigned."),
                        ], spacing=5, scroll=ft.ScrollMode.ADAPTIVE, expand=True),
                        ft.ElevatedButton("Close", on_click=self.close_help)
                    ],
                    expand=True
                ),
                width=550,
                height=500,
                bgcolor="#1E293B",
                border=ft.Border.all(2, ft.Colors.BLUE_ACCENT_700),
                border_radius=15,
                padding=20,
            ),
            alignment=ft.Alignment(0, 0), # Semi-transparent black backdrop
            bgcolor="#88000000", # Semi-transparent black backdrop
            expand=True,
        )
        self.page.overlay.append(self.help_overlay)
        self.page.update()

    def close_help(self, _):
        self.page.overlay.remove(self.help_overlay)
        self.page.update()

    def find_gaps_click(self, _):
        if not self.analysis_results:
            return
        
        # Sort column headers alphanumerically (case-insensitive)
        self.gap_all_columns = sorted([res["column"] for res in self.analysis_results], key=lambda s: s.lower())
        
        # Pre-select columns based on name matching
        start_default = next((c for c in self.gap_all_columns if "begdoc" in c.lower() or "start" in c.lower()), self.gap_all_columns[0])
        end_default = next((c for c in self.gap_all_columns if "enddoc" in c.lower() or "end" in c.lower()), self.gap_all_columns[0])

        # Manual search/filter text field for Start Field
        self.start_search_field = ft.TextField(
            label="Search Start Field Options",
            hint_text="Type to filter start column options...",
            width=300,
            height=40,
            text_size=12,
            content_padding=10,
            border_color=ft.Colors.BLUE_GREY_700,
            focused_border_color=ft.Colors.BLUE_ACCENT,
            on_change=lambda e: self.page.run_task(self.on_start_search_change, e.control.value),
        )

        self.start_dropdown = ft.Dropdown(
            label="Start Control Number Field",
            options=[ft.dropdown.Option(key=c, text=c) for c in self.gap_all_columns],
            value=start_default,
            width=300,
        )
        
        # Manual search/filter text field for End Field
        self.end_search_field = ft.TextField(
            label="Search End Field Options",
            hint_text="Type to filter end column options...",
            width=300,
            height=40,
            text_size=12,
            content_padding=10,
            border_color=ft.Colors.BLUE_GREY_700,
            focused_border_color=ft.Colors.BLUE_ACCENT,
            on_change=lambda e: self.page.run_task(self.on_end_search_change, e.control.value),
        )

        self.end_dropdown = ft.Dropdown(
            label="End Control Number Field",
            options=[ft.dropdown.Option(key=c, text=c) for c in self.gap_all_columns],
            value=end_default,
            width=300,
        )

        self.gaps_dialog = ft.Container(
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Row([
                            ft.Text("Sequence Gap Analysis", size=18, weight=ft.FontWeight.BOLD),
                            ft.IconButton(ft.Icons.CLOSE, on_click=self.close_gaps_dialog)
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Divider(),
                        ft.Text("Select beginning and end fields to check for missing sequences:"),
                        self.start_search_field,
                        self.start_dropdown,
                        ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
                        self.end_search_field,
                        self.end_dropdown,
                        ft.Row([
                            ft.ElevatedButton("Run Gap Check", on_click=lambda e: self.page.run_task(self.execute_gap_analysis)),
                            ft.TextButton("Cancel", on_click=self.close_gaps_dialog)
                        ], spacing=10, alignment=ft.MainAxisAlignment.END)
                    ],
                    spacing=8,
                ),
                width=450,
                height=520,
                bgcolor="#1E293B",
                border=ft.Border.all(2, ft.Colors.BLUE_ACCENT_700),
                border_radius=15,
                padding=20,
            ),
            alignment=ft.Alignment(0, 0),
            bgcolor="#88000000",
            expand=True,
        )
        self.page.overlay.append(self.gaps_dialog)
        self.page.update()

    def close_gaps_dialog(self, _):
        if hasattr(self, 'gaps_dialog') and self.gaps_dialog in self.page.overlay:
            self.page.overlay.remove(self.gaps_dialog)
            self.page.update()

    async def execute_gap_analysis(self):
        start_col = self.start_dropdown.value
        end_col = self.end_dropdown.value
        
        self.close_gaps_dialog(None)
        self.show_loading("Running gap sequence check... please wait.")
        
        try:
            self.gap_results = await asyncio.to_thread(
                find_sequence_gaps, self.selected_file_path, start_col, end_col
            )
            
            # Populate UI Gap Table
            self.gap_results_table.rows.clear()
            for gap in self.gap_results:
                self.gap_results_table.rows.append(
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Text(gap["prefix"])),
                            ft.DataCell(ft.Text(gap["gap_start"])),
                            ft.DataCell(ft.Text(gap["gap_end"])),
                            ft.DataCell(ft.Text(str(gap["missing_count"]))),
                        ]
                    )
                )
            
            self.gap_export_button.disabled = len(self.gap_results) == 0
            
            # Switch to Gap Report Tab explicitly to bring the gap results view into focus
            self.tab_bar.selected_index = 1
            self.tab_bar_view.selected_index = 1
            self.tab_container.selected_index = 1
            
            await self.update_status(f"Gap Check Complete: Found {len(self.gap_results)} gaps.", ft.Colors.GREEN_400)
        except Exception as ex:
            await self.update_status(f"Gap Check failed: {str(ex)}", ft.Colors.RED_400)
            
        gc.collect()
        self.hide_loading()

    async def on_start_search_change(self, value):
        search_val = (value or "").strip().lower()
        
        filtered = [c for c in self.gap_all_columns if search_val in c.lower()]
        
        self.start_dropdown.options = [ft.dropdown.Option(key=c, text=c) for c in filtered]
        
        if self.start_dropdown.value not in filtered:
            self.start_dropdown.value = filtered[0] if filtered else None
            
        self.start_dropdown.update()

    async def on_end_search_change(self, value):
        search_val = (value or "").strip().lower()
        
        filtered = [c for c in self.gap_all_columns if search_val in c.lower()]
        
        self.end_dropdown.options = [ft.dropdown.Option(key=c, text=c) for c in filtered]
        
        if self.end_dropdown.value not in filtered:
            self.end_dropdown.value = filtered[0] if filtered else None
            
        self.end_dropdown.update()

    def on_tab_change(self, e):
        # Keeps selected_index in sync or performs tab navigation changes
        idx = int(e.data)
        self.tab_bar.selected_index = idx
        self.tab_bar_view.selected_index = idx
        self.tab_container.selected_index = idx
        self.page.update()

    async def export_gap_report_click(self, _):
        if not self.gap_results:
            return
            
        filetypes = [("CSV Files", "*.csv")]
        file_path = await asyncio.to_thread(self.pick_file_sync, "Export Gap Report CSV", filetypes, True)
        if not file_path:
            return
            
        try:
            df = pl.DataFrame(self.gap_results)
            df = df.rename({
                "prefix": "Prefix",
                "gap_start": "Gap Start",
                "gap_end": "Gap End",
                "missing_count": "Missing Count"
            })
            df.write_csv(file_path)
            await self.update_status(f"Gap Report exported to {os.path.basename(file_path)}", ft.Colors.GREEN_400)
        except Exception as ex:
            await self.update_status(f"Export failed: {str(ex)}", ft.Colors.RED_400)
        self.page.update()

    async def update_status(self, message, color):
        self.page.snack_bar = ft.SnackBar(ft.Text(message, color=color))
        self.page.snack_bar.open = True
        self.page.update()

async def main(page: ft.Page):
    analyzer = RelativityLoadFileAnalyzer(page)
    await analyzer.initialize()

if __name__ == "__main__":
    import sys
    # Handle assets path for PyInstaller bundling
    if getattr(sys, 'frozen', False):
        # Check both the root and the assets subfolder
        possible_paths = [
            os.path.join(sys._MEIPASS),
            os.path.join(sys._MEIPASS, "assets")
        ]
        assets_path = next((p for p in possible_paths if os.path.exists(os.path.join(p, "companyLogo.png"))), possible_paths[0])
    else:
        # Path when running in debug/dev mode
        assets_path = "assets"
        
    ft.app(target=main, assets_dir=assets_path)

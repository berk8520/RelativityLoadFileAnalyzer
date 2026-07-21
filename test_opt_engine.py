import unittest
import os
import tempfile
from opt_engine import OptDocument, OptDocumentStore, parse_opt_file, parse_lfp_file, parse_dii_file, parse_smi_file, write_opt_file

class TestOptEngine(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def test_opt_document_store(self):
        store = OptDocumentStore()
        doc = OptDocument(doc_id="DOC001", volume_name="VOL1", page_count=2, image_paths=["P1.tif", "P2.tif"], bates_list=["DOC001", "DOC002"])
        store.add_document(doc)

        self.assertEqual(len(store), 1)
        self.assertIsNotNone(store.get_document("DOC001"))
        self.assertEqual(store.get_doc_id_by_bates("DOC002"), "DOC001")

    def test_opt_parser_and_writer(self):
        opt_path = os.path.join(self.test_dir, "sample.opt")
        with open(opt_path, "w", encoding="utf-8") as f:
            f.write('"DOC001","VOL01","IMAGES\\001\\P1.tif","Y","BOX1","FLD1","2"\n')
            f.write('"DOC002","VOL01","IMAGES\\001\\P2.tif","N","","",""\n')

        store = parse_opt_file(opt_path)
        self.assertEqual(len(store), 1)
        doc = store.get_document("DOC001")
        self.assertIsNotNone(doc)
        self.assertEqual(doc.page_count, 2)
        self.assertEqual(len(doc.image_paths), 2)

        out_opt = os.path.join(self.test_dir, "output.opt")
        write_opt_file(out_opt, store)
        self.assertTrue(os.path.exists(out_opt))

    def test_lfp_parser(self):
        lfp_path = os.path.join(self.test_dir, "sample.lfp")
        with open(lfp_path, "w", encoding="utf-8") as f:
            f.write('IM,DOC001,D,0,@VOL01;IMAGES\\001.TIF,3,0\n')
            f.write('IM,DOC002,C,0,@VOL01;IMAGES\\002.TIF,3,0\n')

        store = parse_lfp_file(lfp_path)
        self.assertEqual(len(store), 1)
        doc = store.get_document("DOC001")
        self.assertIsNotNone(doc)
        self.assertEqual(len(doc.image_paths), 2)

    def test_dii_parser(self):
        dii_path = os.path.join(self.test_dir, "sample.dii")
        with open(dii_path, "w", encoding="utf-8") as f:
            f.write('@V VOL01\n@D DOC001\n@I DOC001; IMAGES\\001.TIF\n@I DOC002; IMAGES\\002.TIF\n')

        store = parse_dii_file(dii_path)
        self.assertEqual(len(store), 1)
        doc = store.get_document("DOC001")
        self.assertIsNotNone(doc)
        self.assertEqual(doc.volume_name, "VOL01")
        self.assertEqual(len(doc.image_paths), 2)

if __name__ == "__main__":
    unittest.main()

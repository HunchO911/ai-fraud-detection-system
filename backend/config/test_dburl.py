import unittest

from .dburl import parse_database_url


class ParseDatabaseUrlTests(unittest.TestCase):
    def test_render_style_address(self):
        cfg = parse_database_url("postgresql://fraud:p%40ss@dpg-abc.oregon-postgres.render.com/fraud_detection")
        self.assertEqual(cfg["NAME"], "fraud_detection")
        self.assertEqual(cfg["USER"], "fraud")
        self.assertEqual(cfg["PASSWORD"], "p@ss")  # percent-encoding is decoded
        self.assertEqual(cfg["HOST"], "dpg-abc.oregon-postgres.render.com")
        self.assertEqual(cfg["PORT"], "5432")
        self.assertEqual(cfg["OPTIONS"], {"sslmode": "require"})

    def test_local_address_has_no_ssl_and_keeps_port(self):
        cfg = parse_database_url("postgres://u:p@localhost:5433/db")
        self.assertEqual(cfg["PORT"], "5433")
        self.assertNotIn("OPTIONS", cfg)

    def test_other_databases_are_refused(self):
        with self.assertRaises(ValueError):
            parse_database_url("mysql://u:p@h/db")


if __name__ == "__main__":
    unittest.main()

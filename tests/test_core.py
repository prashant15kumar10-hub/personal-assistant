import os, sys, tempfile, unittest
sys.path.insert(0,os.path.dirname(os.path.dirname(__file__)))
import server
class CoreTests(unittest.TestCase):
    def test_password_hash(self):
        salt,digest=server.hash_password("strong-password")
        self.assertEqual(digest,server.hash_password("strong-password",salt)[1])
        self.assertNotEqual(digest,server.hash_password("wrong-password",salt)[1])
    def test_rate_limit(self):
        server.REQUESTS.clear(); self.assertTrue(server.rate_ok("test-ip"))
    def test_login_page(self):
        self.assertIn("Create account",server.LOGIN_HTML)
        self.assertIn("document.getElementById('name').value",server.LOGIN_HTML)
if __name__=="__main__":unittest.main()

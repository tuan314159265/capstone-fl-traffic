"""Session tampering/expiry and password checks without any cloud access."""
import hashlib
import unittest
from dashboard.auth_server import create_session, valid_session, password_matches


class WebAuth(unittest.TestCase):
    def setUp(self):
        self.config={'username':'tuan','salt':'11'*32,'session_key':'22'*32,'iterations':1000,
            'password_hash':hashlib.pbkdf2_hmac('sha256',b'correct-password',bytes.fromhex('11'*32),1000).hex()}

    def test_signed_session_rejects_tampering_and_expiry(self):
        token=create_session(self.config,3600,timestamp=10000)
        self.assertTrue(valid_session(self.config,token,timestamp=11000))
        self.assertFalse(valid_session(self.config,token,timestamp=14000))
        self.assertFalse(valid_session(self.config,token[:-1]+('a' if token[-1]!='a' else 'b'),timestamp=11000))
        self.assertFalse(valid_session({**self.config,'session_key':'33'*32},token,timestamp=11000))
        self.assertFalse(valid_session(self.config,'bad-token'))

    def test_password_hash(self):
        self.assertTrue(password_matches(self.config,'correct-password'))
        self.assertFalse(password_matches(self.config,'wrong-password'))


if __name__=='__main__':unittest.main()

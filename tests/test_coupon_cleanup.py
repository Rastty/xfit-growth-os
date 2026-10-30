import unittest
from scripts.xfit_coupon_cleanup import stripped,sha
class CouponCleanupTests(unittest.TestCase):
    def test_only_explicit_2022_promo_shortcode_removed(self):
        s=(('Užitečný odstavec. '*40)+
          '[su_button url="https://xfit.cz/damske-obleceni" background="#2def4c"]'
          'FITNESS OBLEČENÍ V AKCI - slevový kód: 5NM2022[/su_button]'
          '<h2>Důležité informace</h2><p>Čtenářská hodnota</p>')
        out,count=stripped(s)
        self.assertEqual(count,1)
        self.assertNotIn("5NM2022",out)
        self.assertIn("<h2>Důležité informace</h2>",out)
    def test_other_coupon_untouched(self):
        original='<p>Aktuální slevový kupon</p>[su_button]KOD2026[/su_button]'
        updated,count=stripped(original)
        self.assertEqual(count,0)
        self.assertEqual(updated,original)
    def test_historical_mention_not_removed(self):
        original='<p>Před lety jsme psali o 5NM2022, který už neplatí.</p>'
        self.assertEqual(stripped(original),(original,0))
    def test_hash_is_deterministic(self):
        self.assertEqual(sha("abc"),sha("abc"))
        self.assertNotEqual(sha("abc"),sha("abd"))

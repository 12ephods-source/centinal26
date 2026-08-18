import unittest

from scripts.ftoe_so10_protected_i_ew_embedding_gate import derive_embedding


class ProtectedIEWEmbeddingGateTests(unittest.TestCase):
    def test_low_energy_embedding_is_derived(self):
        result = derive_embedding()
        self.assertEqual(result["gate"], "DERIVED_LOW_ENERGY_EW_EMBEDDING")
        self.assertTrue(all(result["checks"].values()))
        self.assertEqual(result["derived_SU2LxU1Y_content"], ["2_{-1/2}", "2_{+1/2}"])

    def test_scope_does_not_claim_uv_closure(self):
        result = derive_embedding()
        not_closed = set(result["scientific_scope"]["not_closed"])
        self.assertIn("SO(10) embedding", not_closed)
        self.assertIn("renormalizable SO(10) portal suppression", not_closed)
        self.assertIn("collective or other radiative protection", not_closed)


if __name__ == "__main__":
    unittest.main()

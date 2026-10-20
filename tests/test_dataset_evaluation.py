"""Checks for temporal leakage, zero handling, and timing definitions."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np
from threadpoolctl import threadpool_limits

spec=importlib.util.spec_from_file_location('evaluation',Path(__file__).resolve().parents[1]/'scripts/evaluate_datasets.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class EvaluationTests(unittest.TestCase):
    def test_metrics_include_zeros_except_mape(self):
        e=m.errors(np.array([0.,2.]),np.array([1.,1.]))
        self.assertEqual(e['mae'],1.)
        self.assertEqual(e['mape_nonzero'],50.)
        self.assertEqual(e['wape'],100.)
        self.assertEqual(e['zero_targets'],1)

    def test_future_test_values_cannot_change_prior_predictions(self):
        rng=np.random.default_rng(11)
        train=20+rng.normal(size=500); test=20+rng.normal(size=80)
        changed=test.copy();changed[40:]+=100
        with threadpool_limits(limits=1):
            for h in [1,4]:
                a,p=m.evaluate(train,test,h);b,q=m.evaluate(train,changed,h)
                self.assertEqual(p,q)
                for model in a:
                    np.testing.assert_allclose(a[model][:41],b[model][:41],err_msg=model)
                    self.assertEqual(len(a[model]),len(test)-h+1)
                self.assertEqual(a['persistence'][0],train[-1])

    def test_hw_constant_series(self):
        for h in [1,4]:
            p=m.hw_forecasts(np.full(300,12.),24,h)
            np.testing.assert_allclose(p[48:],12.)

if __name__=='__main__': unittest.main()

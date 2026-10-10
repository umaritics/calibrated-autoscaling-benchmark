import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from simulator import ReactiveAutoscaler, PredictiveAutoscaler, evaluate, run_simulation

class HybridAutoscaler:
    def __init__(self, target_utilization=0.8, window_size=10):
        self.reactive = ReactiveAutoscaler(target_utilization)
        self.predictive = PredictiveAutoscaler(target_utilization)
        self.window_size = window_size
        self.history = []
        self.current_capacity = 10
        self.mode = 'reactive'

    def scale(self, current_demand):
        self.history.append(current_demand)
        if len(self.history) > self.window_size:
            self.history.pop(0)

        # Calculate CV (Coefficient of Variation) to detect spikes
        if len(self.history) > 5:
            mean_demand = np.mean(self.history)
            std_demand = np.std(self.history)
            cv = std_demand / (mean_demand + 1e-9)
            
            # If highly variable / sudden spikes (CV > 0.5), use Reactive to avoid lingering over-provisioning
            if cv > 0.5:
                self.mode = 'reactive'
            else:
                self.mode = 'predictive'
        else:
            self.mode = 'reactive'

        # Keep both internal states updated
        cap_react = self.reactive.scale(current_demand)
        cap_pred = self.predictive.scale(current_demand)
        
        if self.mode == 'reactive':
            self.current_capacity = cap_react
        else:
            self.current_capacity = cap_pred
            
        return self.current_capacity

def main():
    df = pd.read_csv('data/workload_traces.csv')
    regimes = ['spike', 'ramp', 'periodic', 'chaotic']
    
    results = []
    
    for regime in regimes:
        demand = df[regime].values
        
        # Reactive
        reactive = ReactiveAutoscaler()
        prov_re = run_simulation(demand, reactive)
        vio_re, waste_re = evaluate(demand, prov_re)
        
        # Predictive
        predictive = PredictiveAutoscaler()
        prov_pr = run_simulation(demand, predictive)
        vio_pr, waste_pr = evaluate(demand, prov_pr)
        
        # Hybrid
        hybrid = HybridAutoscaler()
        prov_hy = run_simulation(demand, hybrid)
        vio_hy, waste_hy = evaluate(demand, prov_hy)
        
        results.append({'Regime': regime, 'Policy': 'Calibrated Reactive', 'SLA Violation Rate': vio_re, 'Wasted Capacity': waste_re})
        results.append({'Regime': regime, 'Policy': 'Predictive (SMA)', 'SLA Violation Rate': vio_pr, 'Wasted Capacity': waste_pr})
        results.append({'Regime': regime, 'Policy': 'Proposed Hybrid', 'SLA Violation Rate': vio_hy, 'Wasted Capacity': waste_hy})
        
        # Plot
        plt.figure(figsize=(10, 4))
        plt.plot(df['time'], demand, label='Demand', alpha=0.7)
        plt.plot(df['time'], prov_re, label='Reactive Provisioned', alpha=0.5, linestyle='--')
        plt.plot(df['time'], prov_hy, label='Hybrid Provisioned', alpha=0.9)
        plt.title(f'Regime: {regime}')
        plt.legend()
        plt.savefig(f'output/{regime}_comparison.png')
        plt.close()
        
    res_df = pd.DataFrame(results)
    res_df.to_csv('output/final_comparison.csv', index=False)
    print(res_df.to_markdown())

if __name__ == '__main__':
    main()

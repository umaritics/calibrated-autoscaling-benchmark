import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from statsmodels.tsa.holtwinters import ExponentialSmoothing
import os

class ReactiveAutoscaler:
    def __init__(self, target_utilization=0.8, cooldown=5):
        self.target_utilization = target_utilization
        self.cooldown = cooldown
        self.cooldown_counter = 0
        self.current_capacity = 10 # starting capacity

    def scale(self, current_demand):
        if self.cooldown_counter > 0:
            self.cooldown_counter -= 1
            return self.current_capacity
        
        utilization = current_demand / self.current_capacity
        if utilization > self.target_utilization:
            # scale up
            desired = current_demand / self.target_utilization
            self.current_capacity = desired
            self.cooldown_counter = self.cooldown
        elif utilization < (self.target_utilization - 0.2):
            # scale down
            desired = current_demand / self.target_utilization
            self.current_capacity = max(10, desired)
            self.cooldown_counter = self.cooldown
            
        return self.current_capacity

class PredictiveAutoscaler:
    def __init__(self, target_utilization=0.8, history_size=20):
        self.target_utilization = target_utilization
        self.history = []
        self.history_size = history_size
        self.current_capacity = 10

    def scale(self, current_demand):
        self.history.append(current_demand)
        if len(self.history) > self.history_size:
            self.history.pop(0)
            
        if len(self.history) < 5:
            # not enough history, behave like reactive without cooldown
            self.current_capacity = max(10, current_demand / self.target_utilization)
            return self.current_capacity
            
        # simple moving average prediction for next step
        prediction = np.mean(self.history)
        # weight prediction and current demand
        expected_demand = max(prediction, current_demand)
        
        self.current_capacity = max(10, expected_demand / self.target_utilization)
        return self.current_capacity

def run_simulation(trace, autoscaler):
    provisioned = []
    current_cap = 10
    for demand in trace:
        provisioned.append(current_cap)
        current_cap = autoscaler.scale(demand)
    return np.array(provisioned)

def evaluate(demand, provisioned):
    # SLA violation: demand > provisioned (assuming capacity is 1:1 with demand for simplicity)
    violations = np.sum(demand > provisioned)
    violation_rate = violations / len(demand)
    
    # Over-provisioning: provisioned - demand
    wasted = np.sum(np.maximum(0, provisioned - demand))
    
    return violation_rate, wasted

def main():
    df = pd.read_csv('data/workload_traces.csv')
    regimes = ['spike', 'ramp', 'periodic', 'chaotic']
    
    results = []
    os.makedirs('output', exist_ok=True)
    
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
        
        results.append({
            'Regime': regime,
            'Policy': 'Calibrated Reactive',
            'SLA Violation Rate': vio_re,
            'Wasted Capacity': waste_re
        })
        results.append({
            'Regime': regime,
            'Policy': 'Predictive (SMA)',
            'SLA Violation Rate': vio_pr,
            'Wasted Capacity': waste_pr
        })
        
        # Plot
        plt.figure(figsize=(10, 4))
        plt.plot(df['time'], demand, label='Demand', alpha=0.7)
        plt.plot(df['time'], prov_re, label='Reactive Provisioned', alpha=0.7)
        plt.plot(df['time'], prov_pr, label='Predictive Provisioned', alpha=0.7)
        plt.title(f'Regime: {regime}')
        plt.legend()
        plt.savefig(f'output/{regime}_baseline.png')
        plt.close()
        
    res_df = pd.DataFrame(results)
    res_df.to_csv('output/baseline_results.csv', index=False)
    print(res_df)

if __name__ == '__main__':
    main()

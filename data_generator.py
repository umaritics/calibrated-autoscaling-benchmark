import numpy as np
import pandas as pd
import os

def generate_traces(num_steps=1000, base_load=10):
    time = np.arange(num_steps)
    np.random.seed(42)
    
    # 1. Sudden Spike: mostly stable, occasional huge spikes
    spike = np.ones(num_steps) * base_load
    for _ in range(5):
        idx = np.random.randint(100, num_steps-100)
        spike[idx:idx+10] = base_load * 5
        
    # 2. Gradual Ramp: linearly increasing load
    ramp = np.linspace(base_load, base_load * 4, num_steps)
    
    # 3. Periodic: diurnal or seasonal pattern
    periodic = base_load + (base_load * 0.8) * np.sin(2 * np.pi * time / 200)
    
    # 4. Chaotic: random walk / high variance
    chaotic = base_load + np.cumsum(np.random.normal(0, 1.5, num_steps))
    chaotic = np.clip(chaotic, 1, None) # keep positive
    
    df = pd.DataFrame({
        'time': time,
        'spike': spike,
        'ramp': ramp,
        'periodic': periodic,
        'chaotic': chaotic
    })
    
    os.makedirs('data', exist_ok=True)
    df.to_csv('data/workload_traces.csv', index=False)
    print("Workload traces generated successfully at data/workload_traces.csv")

if __name__ == '__main__':
    generate_traces()

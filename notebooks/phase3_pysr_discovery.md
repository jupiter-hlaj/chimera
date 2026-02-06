# 🔬 Chimera Phase 3: Symbolic Regression with PySR

> **Environment**: Run this notebook in SageMaker Studio Lab (free tier)
> **Purpose**: Discover mathematical formulas that explain market-environment correlations

## Setup Instructions

1. **Get SageMaker Studio Lab Account**: https://studiolab.sagemaker.aws
2. **Install Julia** (required for PySR):
   ```bash
   !pip install pysr
   !julia -e 'using Pkg; Pkg.add("SymbolicRegression")'
   ```
3. **Upload Data**: Download `latest_aligned.json` from S3 and upload here

---

## Step 1: Load the Aligned Dataset

```python
import pandas as pd
import numpy as np
import json
import boto3

# Option A: Load from S3 (if AWS credentials configured)
# s3 = boto3.client('s3')
# obj = s3.get_object(Bucket='chimera-processed-dev-821891894512', Key='latest_aligned.json')
# data = json.loads(obj['Body'].read())

# Option B: Load from uploaded file
with open('latest_aligned.json', 'r') as f:
    data = json.load(f)

df = pd.DataFrame(data)
df['timestamp'] = pd.to_datetime(df['timestamp'])
df = df.set_index('timestamp').sort_index()

print(f"Shape: {df.shape}")
print(f"Columns: {list(df.columns)}")
df.head()
```

---

## Step 2: Prepare Features and Targets

```python
# Separate market columns (targets) from environmental factors (features)
market_cols = [c for c in df.columns if c.startswith('market_')]
env_cols = [c for c in df.columns if not c.startswith('market_')]

# Pick target: VIX Close (volatility) or SPY returns
target = 'market_vix_close'  # Change this as needed
y = df[target].dropna()

# Use all environmental factors as features
X = df[env_cols].reindex(y.index).dropna(axis=1, how='all')

# Align indices
idx = X.index.intersection(y.index)
X = X.loc[idx].fillna(method='ffill').fillna(0)
y = y.loc[idx]

print(f"Features: {X.shape[1]}")
print(f"Samples: {len(y)}")
```

---

## Step 3: Run Symbolic Regression

```python
from pysr import PySRRegressor

# Configure PySR
model = PySRRegressor(
    niterations=40,                    # Increase for better results
    binary_operators=["+", "-", "*", "/"],
    unary_operators=["sin", "cos", "exp", "log", "sqrt"],
    populations=12,
    ncyclesperiteration=550,
    maxsize=25,                         # Max equation complexity
    procs=4,                            # Parallel processes
    timeout_in_seconds=600,             # 10 minute timeout
    loss="loss(x, y) = (x - y)^2",      # MSE loss
    turbo=True,                         # Speed optimization
    progress=True
)

# Fit the model
model.fit(X.values, y.values, variable_names=list(X.columns))
```

---

## Step 4: Explore Discovered Equations

```python
# View Pareto front (best equations at each complexity level)
print(model)

# Get the best equation
best = model.get_best()
print(f"\n🏆 Best Equation:")
print(f"   {best['equation']}")
print(f"   Score: {best['score']:.4f}")
print(f"   Complexity: {best['complexity']}")
```

---

## Step 5: Validate Predictions

```python
import matplotlib.pyplot as plt

# Predict using discovered formula
y_pred = model.predict(X.values)

# Plot actual vs predicted
plt.figure(figsize=(14, 5))
plt.subplot(1, 2, 1)
plt.plot(y.index, y.values, label='Actual', alpha=0.7)
plt.plot(y.index, y_pred, label='Predicted', alpha=0.7)
plt.legend()
plt.title(f'{target}: Actual vs Predicted')
plt.xlabel('Date')
plt.ylabel('Value')

plt.subplot(1, 2, 2)
plt.scatter(y.values, y_pred, alpha=0.5, s=20)
plt.plot([y.min(), y.max()], [y.min(), y.max()], 'r--', label='Perfect fit')
plt.xlabel('Actual')
plt.ylabel('Predicted')
plt.title('Correlation Plot')
plt.legend()

plt.tight_layout()
plt.show()

# R² score
from sklearn.metrics import r2_score
print(f"R² Score: {r2_score(y, y_pred):.4f}")
```

---

## Step 6: Export Rules

```python
# Export discovered equations as a rule table
rules = []
for i, row in model.equations_.iterrows():
    rules.append({
        'complexity': row['complexity'],
        'loss': row['loss'],
        'equation': row['equation'],
        'score': row['score']
    })

# Save to JSON
import json
with open('discovered_rules.json', 'w') as f:
    json.dump(rules, f, indent=2)

print("✅ Rules exported to discovered_rules.json")
```

---

## Notes

- **Schumann Resonance + VIX**: Early correlations suggest r=0.52+ at 1-hour lag
- **Lag Features**: Consider adding shifted columns (e.g., `schumann_t-1h`) for predictive formulas
- **Normalization**: PySR handles raw values, but normalizing can improve speed
- **Complexity vs Accuracy**: Start with lower `maxsize` and increase if needed

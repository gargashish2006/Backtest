
import pandas as pd
import numpy as np
import joblib
from pathlib import Path
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score

def train_model():
    repo_root = Path(__file__).parent
    data_path = repo_root / "data/ml_dataset_2017_2022_v2.csv"
    
    if not data_path.exists():
        print("V2 Dataset not found. Please run ml_dataset_gen.py first.")
        return
        
    print("Loading V2 Dataset...")
    df = pd.read_csv(data_path)
    print(f"Loaded {len(df)} rows.")
    
    # Features V2
    features = [
        'sh_decrease_4q_binary', 
        'sh_decrease_6q_binary', 
        'sh_decrease_8q_binary', 
        'rsnp_6m', 
        'rsnp_1y', 
        'rsnp_2y',
        # Contextual Features
        'ind_sh_breadth',
        'grp_sh_breadth',
        'ind_rsnp_1y',
        'grp_rsnp_1y'
    ]
    
    target = 'target_3m_return'
    
    # Handle Missing Values
    # RSNP might be NaN if history not long enough.
    # Shareholder stats might be NaN.
    # We drop rows with missing features for training.
    df_clean = df.dropna(subset=features + [target])
    print(f"Rows after cleaning: {len(df_clean)}")
    
    X = df_clean[features]
    y = df_clean[target]
    
    # Train/Validation Split (Time-based preferred, but here we just want to validate)
    # Let's use simple random split for validation of hyperparameters, 
    # but re-train on full set for final model.
    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)
    
    print("Training Random Forest Regressor (V2)...")
    # Configurable params
    model = RandomForestRegressor(
        n_estimators=100,
        max_depth=10,
        min_samples_leaf=20,
        random_state=42,
        n_jobs=-1
    )
    
    model.fit(X_train, y_train)
    
    # Evaluate
    preds = model.predict(X_val)
    mse = mean_squared_error(y_val, preds)
    r2 = r2_score(y_val, preds)
    
    print(f"Validation MSE: {mse:.6f}")
    print(f"Validation R2: {r2:.6f}")
    
    # Feature Importance
    importances = model.feature_importances_
    feat_imp = pd.DataFrame({'feature': features, 'importance': importances})
    feat_imp = feat_imp.sort_values('importance', ascending=False)
    print("\nFeature Importance (V2):")
    print(feat_imp)
    
    # Retrain on Full Data
    print("\nRetraining on full 2017-2022 dataset...")
    final_model = RandomForestRegressor(
        n_estimators=100,
        max_depth=10,
        min_samples_leaf=20,
        random_state=42,
        n_jobs=-1
    )
    final_model.fit(X, y)
    
    # Save Model
    models_dir = repo_root / "models"
    models_dir.mkdir(exist_ok=True)
    model_path = models_dir / "ml_model_rf_v2.pkl"
    joblib.dump(final_model, model_path)
    print(f"Model saved to {model_path}")

if __name__ == "__main__":
    train_model()

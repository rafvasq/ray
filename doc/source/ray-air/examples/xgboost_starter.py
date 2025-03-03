# flake8: noqa
# isort: skip_file

# __air_generic_preprocess_start__
import ray
from ray.data.preprocessors import StandardScaler
from ray.air import train_test_split

# Load data.
import pandas as pd

bc_df = pd.read_csv(
    "https://air-example-data.s3.us-east-2.amazonaws.com/breast_cancer.csv"
)
dataset = ray.data.from_pandas(bc_df)
# Optionally, read directly from s3
# dataset = ray.data.read_csv("s3://air-example-data/breast_cancer.csv")

# Split data into train and validation.
train_dataset, valid_dataset = train_test_split(dataset, test_size=0.3)

# Create a test dataset by dropping the target column.
test_dataset = valid_dataset.map_batches(
    lambda df: df.drop("target", axis=1), batch_format="pandas"
)

# Create a preprocessor to scale some columns
columns_to_scale = ["mean radius", "mean texture"]
preprocessor = StandardScaler(columns=columns_to_scale)
# __air_generic_preprocess_end__


# __air_xgb_train_start__
from ray.train.xgboost import XGBoostTrainer

trainer = XGBoostTrainer(
    scaling_config={
        # Number of workers to use for data parallelism.
        "num_workers": 2,
        # Whether to use GPU acceleration.
        "use_gpu": False,
    },
    label_column="target",
    num_boost_round=20,
    params={
        # XGBoost specific params
        "objective": "binary:logistic",
        "eval_metric": ["logloss", "error"],
    },
    datasets={"train": train_dataset, "valid": valid_dataset},
    preprocessor=preprocessor,
)
result = trainer.fit()
print(result.metrics)
# __air_xgb_train_end__

# __air_xgb_tuner_start__
from ray import tune

param_space = {"params": {"max_depth": tune.randint(1, 9)}}
metric = "train-logloss"
# __air_xgb_tuner_end__

# __air_tune_generic_end__
from ray.tune.tuner import Tuner, TuneConfig

tuner = Tuner(
    trainer,
    param_space=param_space,
    tune_config=TuneConfig(num_samples=5, metric=metric, mode="min"),
)
result_grid = tuner.fit()
best_result = result_grid.get_best_result()
print("Best result:", best_result)
# __air_tune_generic_end__

# __air_xgb_batchpred_start__
from ray.train.batch_predictor import BatchPredictor
from ray.train.xgboost import XGBoostPredictor

# You can also create a checkpoint from a trained model using `to_air_checkpoint`.
checkpoint = best_result.checkpoint

batch_predictor = BatchPredictor.from_checkpoint(checkpoint, XGBoostPredictor)

predicted_probabilities = batch_predictor.predict(test_dataset)
print("PREDICTED PROBABILITIES")
predicted_probabilities.show()
# {'predictions': 0.9970690608024597}
# {'predictions': 0.9943051934242249}
# {'predictions': 0.00334902573376894}
# __air_xgb_batchpred_end__

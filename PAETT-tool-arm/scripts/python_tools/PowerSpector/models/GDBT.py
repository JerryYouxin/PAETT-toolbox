from .model import ModelBase
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import GradientBoostingRegressor

class GBDTModel(ModelBase):
    def init(self):
        print("INFO: Initializing GBDT model")
        model = Pipeline([('std',StandardScaler()),('model',GradientBoostingRegressor(loss='huber', learning_rate=0.1, n_estimators=80, subsample=0.8, max_depth=3, min_samples_split=130, min_samples_leaf=30, max_features=7, random_state=89))])
        return model
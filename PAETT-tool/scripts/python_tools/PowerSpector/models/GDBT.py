from .model import ModelBase
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.neural_network import GradientBoostingRegressor

class MLPModel(ModelBase):
    def __init__(self):
        super.__init__()
        self.init()

    def init(self, num=55, hidden=(16,16,16)):
        ModelBase.model = Pipeline([('std',StandardScaler()),('model',GradientBoostingRegressor(loss='huber', learning_rate=0.1, n_estimators=80, subsample=0.8, max_depth=3, min_samples_split=130, min_samples_leaf=30, max_features=7, random_state=89))])
from random import Random

class ParamNames:
    widthOffset = "WidthOffset"
    heightOffset = "HeightOffset"
    precision = "Precision"
    seamAbberations = "Seam Abberations"

    amount = "Amount"
    probability = "Probability"

    seed = "Seed"

class Keywords:
    layerNumber = "layerNumber"

class BiasedCoin:
    def __init__(self, seed):
        self.randGenerator = Random()
        self.randGenerator.seed = seed

    def toss(self, headProb):
        weights = [100-headProb, headProb]
        return self.randGenerator.choices([0,1], weights=weights)[0]

    def uniform(self,a,b):
        return self.randGenerator.uniform(a,b)
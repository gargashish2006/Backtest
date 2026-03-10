from abc import ABC, abstractmethod

class Strategy(ABC):
    @abstractmethod
    def generate_signals(self, data):
        pass

    @abstractmethod
    def backtest(self, data):
        pass
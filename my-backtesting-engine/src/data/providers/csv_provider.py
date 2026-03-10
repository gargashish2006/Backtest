class CSVDataProvider:
    def __init__(self, file_path):
        self.file_path = file_path
        self.data = None

    def read_csv(self):
        import pandas as pd
        self.data = pd.read_csv(self.file_path)

    def get_data(self):
        if self.data is None:
            self.read_csv()
        return self.data
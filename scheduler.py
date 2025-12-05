class Scheduler:
    def __init__(self, json_repo, sqlite_repo, classifier, rule_engine, recommender):
        self.json_repo = json_repo
        self.sqlite = sqlite_repo
        self.classifier = classifier
        self.rules = rule_engine
        self.recommender = recommender

    def process_new_sessions(self):

        pass

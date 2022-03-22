from flask import Flask
from home.views import home_view
import itertools
from splitwise import Splitwise

@app.route("/")
def home():
	return "this is the main page"

def create_app(config_file):
	app = Flask(__name__)  # Create application object
	app.config.from_pyfile(config_file)  # Configure application with settings file, not strictly necessary
	app.register_blueprint(home_view)  # Register url's so application knows what to do
	return app

# TODO: get people and debts from Splitwise API
splitwise_instance = Splitwise("iA4axoPLQVBOUOilnnS9XTNATl24sjOQITrNIt2h","ffBc3UncyGtK8dS6coOOc7EiJz4qMW2zHjE6Cu0B")
url, secret = splitwise_instance.getAuthorizeURL()

print(url,secret)

# Code for simplifying debt taken from https://terbium.io/2020/09/debt-simplification/

people = ["Grace", "Ivan", "Judy", "Luke", "Mallory"]
debts = [
    ("Grace", "Ivan", 5),
    ("Grace", "Judy", 3),
    ("Ivan", "Grace", 2),
    ("Ivan", "Mallory", 5),
    ("Judy", "Grace", 10),
    ("Judy", "Luke", 4),
    ("Judy", "Mallory", 6),
    ("Judy", "Mallory", 2),
    ("Luke", "Ivan", 4),
    ("Mallory", "Grace", 15),
    ("Mallory", "Luke", 6),
    ("Mallory", "Judy", 11),
]

def show_transactions(transactions):
    for (debtor, creditor, value) in transactions:
        if value > 0:
            print(f"{debtor} owes {creditor} ${value}")
        else:
            print(f"{creditor} owes {debtor} ${-value}")

def compute_balances(debts):
    balances = {person: 0 for person in people}
    for (debtor, creditor, value) in debts:
        balances[debtor] -= value
        balances[creditor] += value
    return balances

def simplify_with_collector(balances):
    collector = next(iter(balances.keys()))
    return [(collector, person, balance) for (person, balance)
            in balances.items() if person != collector]

def find_zero_subset(balances):
    for i in range(1, len(balances)):
        for subset in itertools.combinations(balances.items(), i):
            if sum([balance[1] for balance in subset]) == 0:
                return [balance[0] for balance in subset]
    return None

def simplify_debts(debts):
	remaining_set = compute_balances(debts)
	subsets = []
	while (subset := find_zero_subset(remaining_set)) is not None:
	    subsets.append(subset)
	    remaining_set = {x[0]: x[1] for x in remaining_set.items() if x[0] not in subset}
	subsets.append(list(remaining_set.keys()))

	balances = compute_balances(debts)
	optimal_transactions = []
	for subset in subsets:
	    subset_balances = {person: balances[person] for person in subset}
	    optimal_transactions.extend(simplify_with_collector(subset_balances))	
	return optimal_transactions


if __name__ == "__main__":

	show_transactions(simplify_debts(debts))	
	app = create_app('settingslocal.py')  # Create application with our config file
	app.run()  # Run our application

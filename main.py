from flask import Flask, redirect, request, url_for, session
from home.views import home_view
import itertools
from splitwise import Splitwise	
import requests
import numpy as np

app = Flask(__name__)  # Create application object

# Splitwise credentials
client_id = "iA4axoPLQVBOUOilnnS9XTNATl24sjOQITrNIt2h"
s = Splitwise(client_id,"ffBc3UncyGtK8dS6coOOc7EiJz4qMW2zHjE6Cu0B")
group_id = 12328749

@app.route("/")
def home():
	return authorize()

@app.route('/welcome')
def render_welcome():
	user = s.getCurrentUser()

	#groups = s.getGroups()
	#print([(group.getName(),group.getId()) for group in groups])

	expenses = s.getExpenses(group_id=group_id,limit=255)
	group = s.getGroup(group_id)
	global currency
	currency = group.country_code if group.country_code else 'CAD'
	global people
	people = [user.getFirstName() for user in group.getMembers()]
	people_dict = {user.getId():user.getFirstName() for user in group.getMembers()}
	formatted_expenses = [[(people_dict[payment.getFromUser()],
		people_dict[payment.getToUser()],
		payment.getAmount()) for payment in expense.getRepayments() if payment.getFromUser() in people_dict and payment.getToUser() in people_dict] for expense in expenses]
	
	formatted_expenses = [e for e in formatted_expenses if len(e) != 0]

	debts = np.concatenate(formatted_expenses)

	#getCurrencyCode

	return(f'Welcome {user.getFirstName()}<br>\
			Your preferred currency is: {currency}<br>\
			Your group users are: {people}<br>\
			Your current expenses are: {show_transactions(simplify_debts(debts))}')

@app.route("/authorize")
def authorize():
	'''
	try:
		with open('credentials.txt','r') as cred_file:
			access_token = cred_file.readlines()
			s.setAccessToken(eval(access_token))
			return render_welcome()
	except Exception as e:
		print(f'{e}, trying redirect...')
 	'''
	global oauth_token_secret
	url, oauth_token_secret = s.getAuthorizeURL()
	return redirect(url)

@app.route("/authorize/callback")
def authorize_callback():
	oauth_token    = request.args.get('oauth_token')
	oauth_verifier = request.args.get('oauth_verifier')
	#global access_token
	access_token   = s.getAccessToken(oauth_token, oauth_token_secret, oauth_verifier)
	s.setAccessToken(access_token)

	#with open('credentials.txt','w') as cred_file:
	#	cred_file.write(str(access_token))

	return render_welcome()


def create_app(config_file):
	app.config.from_pyfile(config_file)  # Configure application with settings file, not strictly necessary
	app.register_blueprint(home_view)  # Register url's so application knows what to do
	return app

# Code for simplifying debt taken from https://terbium.io/2020/09/debt-simplification/

def show_transactions(transactions):
	transaction_list = []
	for (debtor, creditor, value) in transactions:
		if value > 0:
			transaction_list.append(f"{debtor} owes {creditor} ${value}")
		else:
			transaction_list.append(f"{creditor} owes {debtor} ${-value}")
	return transaction_list

def compute_balances(debts):
    balances = {person: 0 for person in people}
    for (debtor, creditor, value) in debts:
        balances[debtor] -= float(value)
        balances[creditor] += float(value)
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

	a = create_app('settingslocal.py')  # Create application with our config file
	a.run()  # Run our application

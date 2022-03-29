from flask import Flask, redirect, request, render_template
import requests
import pandas as pd
from home.views import home_view
import itertools
from splitwise import Splitwise	
import numpy as np
from coinapi_rest_v1.restapi import CoinAPIv1
import ssl
from nomics import Nomics

ssl._create_default_https_context = ssl._create_unverified_context

app = Flask(__name__,template_folder='templates')  # Create application object

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
	simplified_debts = simplify_debts(debts)


	#convert transactions
	cryptocurrency = 'ETH'
	exchange_rates = get_rates(currency,cryptocurrency)
	median_exchange_rate = get_median_rate(exchange_rates)
	converted_debts = convert_transactions(simplified_debts,median_exchange_rate)

	return render_template('index.html', name=user.getFirstName(), currency=currency, expenses=show_transactions(simplified_debts,currency))


	# return(f"Welcome {user.getFirstName()}<br>\
	# 		Your preferred currency is: {currency}<br>\
	# 		Your group users are: {people}<br>\
	# 		Your current expenses are: {show_transactions(simplified_debts,currency)}<br>\
	# 		Today's exchange rates are:{exchange_rates}<br>\
	# 		Your converted expenses are:{show_transactions(converted_debts,cryptocurrency)}")

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

# Page 2 - Crypto Information Submission
@app.route('/crypto_submit')
def submit_crypto():
	user = s.getCurrentUser()

	currency_form = request.args.get('currency')
	#currency_form is in lower case. Need to make it upper case for the get_rates function!
	exchange_rates_tuples = get_rates(currency,currency_form.upper())
	# List of tuples in form of: ('CAD', 'ETH', 0.00023622043649828227)
	exchange_rates = [x[2] for x in exchange_rates_tuples]
	median_exchange_rate = get_median_rate(exchange_rates_tuples)

	global people
	expenses = s.getExpenses(group_id=group_id,limit=255)
	group = s.getGroup(group_id)
	people = [user.getFirstName() for user in group.getMembers()]
	people_dict = {user.getId():user.getFirstName() for user in group.getMembers()}
	formatted_expenses = [[(people_dict[payment.getFromUser()],
		people_dict[payment.getToUser()],
		payment.getAmount()) for payment in expense.getRepayments() if payment.getFromUser() in people_dict and payment.getToUser() in people_dict] for expense in expenses]
	
	formatted_expenses = [e for e in formatted_expenses if len(e) != 0]

	debts = np.concatenate(formatted_expenses)
	simplified_debts = simplify_debts(debts)
	converted_debts = convert_transactions(simplified_debts,median_exchange_rate)


	return render_template('crypto_submit.html',name=user.getFirstName(),currency=currency_form, rates=exchange_rates, median_rate=median_exchange_rate, converted_expenses=show_crypto_transactions(converted_debts,currency_form.upper()))

# Page 3 - Summary/Confirmation of transaction
@app.route('/transaction_confirmation')
def confirmation():
	return render_template('confirmation.html')


def create_app(config_file):
	app.config.from_pyfile(config_file)  # Configure application with settings file, not strictly necessary
	app.register_blueprint(home_view)  # Register url's so application knows what to do
	return app

# Code for getting exchange rates
def get_coinlayer_rate(from_currency,to_currency):
    api_key = '0e7274782bc1bbd5cff98b0b0f3eee58'

    date = pd.to_datetime('today').date()

    prices = []
    try:
        api_url = f'http://api.coinlayer.com/{date}&symbols={to_currency}&target={from_currency}?access_key={api_key}'
        raw = requests.get(api_url).json()
        val = []
        val.append(raw['rates'])
        price = val[0][f'{to_currency}']
    except Exception as e:
    	price = np.nan

    return (from_currency,to_currency, 1.0/price)	

def get_nomics_rate(from_currency,to_currency):
	key = '278552191c1f206e5389c4770ce07214a6f23ea3'
	nomics = Nomics(key)
	data = nomics.Currencies.get_currencies(ids = to_currency,convert=from_currency)
	return (from_currency,to_currency,1.0/float(data[0]['price']))

def get_coin_api_rate(from_currency,to_currency):
	key = 'B65AF4B5-9E76-4833-A220-733C6259FEF5'
	api = CoinAPIv1(key)

	data = api.exchange_rates_get_specific_rate(from_currency, to_currency)

	return (from_currency, to_currency, data['rate'])

def get_rates(from_currency,to_currency):
	exchanges = [get_coin_api_rate,get_nomics_rate,get_coinlayer_rate]

	rates = [exchange(from_currency,to_currency) for exchange in exchanges]
	return rates

def get_median_rate(exchange_rates):
	values = [rate[-1] for rate in exchange_rates if not np.isnan(rate[-1])]
	return np.median(values)

def convert_transactions(transactions,exchange_rate):
	transaction_list = []
	for (debtor, creditor, value) in transactions:
		if value > 0:
			transaction_list.append((debtor,creditor,exchange_rate*value))
		else:
			transaction_list.append((creditor,debtor,-exchange_rate*value))
	return transaction_list

# Code for simplifying debt taken from https://terbium.io/2020/09/debt-simplification/

def show_transactions(transactions, currency_code):
	transaction_list = []
	for (debtor, creditor, value) in transactions:
		if value > 0:
			transaction_list.append(f"{debtor} owes {creditor} {round(value,2)} {currency_code}")
		else:
			transaction_list.append(f"{creditor} owes {debtor} {round(-value,2)} {currency_code}")
	return transaction_list

def show_crypto_transactions(transactions, cryptocurrency_code):
	transaction_list = []
	for (debtor, creditor, value) in transactions:
		if value > 0:
			transaction_list.append(f"{debtor} owes {creditor} {round(value,6)} {cryptocurrency_code}")
		else:
			transaction_list.append(f"{creditor} owes {debtor} {round(-value,6)} {cryptocurrency_code}")
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

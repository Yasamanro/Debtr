from flask import Flask

app = flask (__name__)

@app.route("/")
def home():
	return "this is the main page"

if __name__ == "__main__":
	app.run()
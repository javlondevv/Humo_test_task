mig:
	python3 manage.py makemigrations
	python3 manage.py migrate
unmig:
	find . -path "*/migrations/0*.py" -not -name "__init__.py" -delete

pip-install:
	python3 -m pip install -r requirements.txt
pip-update:
	python3 -m pip install -r requirements.txt --upgrade
pip-freeze:
	python3 -m pip freeze > requirements.txt
secret-key:
	python3 -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
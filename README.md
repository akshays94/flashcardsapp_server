# flashcardsapp_server

## How to run the server

### Create a new virtual environment
```
python3 -m venv flashcardsapp-venv
```

### Activate the virtual environment
```
source flashcardsapp-venv/bin/activate
```

### Install the requirements
```
python3 -m pip install requirements.txt
```

### Run the server
```
uvicorn main:app --reload --port 8002
```

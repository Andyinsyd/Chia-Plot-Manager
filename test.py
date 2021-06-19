import requests

headers={'Content-type':'application/json', 'Accept':'application/json'}
url = "http://localhost:57097/api/Plot/Create";

plot = {
    'jobName': 'sas1',
    'kSize': 32,
    'totalSeconds': 255,
    'phase1Seconds': 48,
    'phase2Seconds': 44,
    'phase3Seconds': 438,
    'phase4Seconds': 428,
    'copySeconds': 48,
    'machine': '7700'
    }

x = requests.post(url, json=plot, headers = headers)

print(x.text);
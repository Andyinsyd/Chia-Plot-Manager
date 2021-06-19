import requests

headers={'Content-type':'application/json', 'Accept':'application/json'}
url = "http://192.168.0.173:5000/api/Plot/Create"

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

print(x.text)
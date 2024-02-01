# Sextant

*Navigate through astronomical events*

* version: unstable

Install in a venv:
```
python3 -m venv venv
source venv/bin/activate
pip install git+https://...
sextant --help
```

Configure endpoints:
```
$ cat ~/.config/sextant/config.yaml
contexts:
  default:
    splunk:
      endpoint: https://<instance>.splunkcloud.com:8089
      auth:
        type: 1password
        item: <item.id>

    thehive:
      endpoint: https://<url>
      auth:
        type: 1password
        item: <item.id>

    sentinelone:
      endpoint: https://<instance>.sentinelone.net
      auth:
        type: 1password
        item: <item.id>
```

Check connections:
```
$ sextant --status
splunk True
thehive True
s1 True
```

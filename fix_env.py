with open('.env','r') as f: lines=f.readlines();
with open('.env','w') as f:
    for l in lines:
        if l.startswith('VK_TOKEN='): f.write(f'VK_TOKEN={next(x.split("=")[1] for x in lines if x.startswith("VK_USER_TOKEN="))}')
        else: f.write(l)

print('hello')
body = {
    "images": {
        f"image{1}": 'blah',
        f"image{2}": 'blah blah'
    }
}

print(len(body.get("images")))


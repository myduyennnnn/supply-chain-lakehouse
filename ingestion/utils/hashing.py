import hashlib


def calculate_file_hash(path):

    md5 = hashlib.md5()

    with open(path, "rb") as f:

        while chunk := f.read(8192):
            md5.update(chunk)

    return md5.hexdigest()
import os

import pytest
import requests


class YaUploader:
    base_url = 'https://cloud-api.yandex.net/v1/disk/resources'
    upload_url = 'https://cloud-api.yandex.net/v1/disk/resources/upload'

    def __init__(self, token=None):
        self.token = token if token else os.getenv('YANDEX_DISK_TOKEN')
        if not self.token:
            raise ValueError("нужен токен")

    def get_folder(self, path):
        headers = self._get_headers()
        response = requests.get(f'{self.base_url}?path={path}', headers=headers)
        return response

    def create_folder(self, path):
        headers = self._get_headers()
        folder_not_created = False
        response = requests.put(f'{self.base_url}?path={path}', headers=headers)
        assert response.status_code == 201

    def upload_photos_to_yd(self, path, url_file, name):
        headers = self._get_headers()
        params = {"path": f'/{path}/{name}', 'url': url_file, "overwrite": "true"}
        response = requests.post(self.upload_url, headers=headers, params=params)
        assert response.status_code == 202
        self._wait(response)

    def delete_folder(self, path):
        headers = self._get_headers()
        params = {
            'path': path
        }
        response = requests.delete(self.base_url, headers=headers, params=params)
        assert response.status_code in [204, 202, 404]
        if response.status_code == 202:
            self._wait(response)

    def _wait(self, response):
        not_success = False
        while not_success:
            url = response.json()['href']
            response = requests.get(url=url, headers=self._get_headers())
            not_success = response.json()['status'] != 'success'

    def _get_headers(self):
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': f'OAuth {self.token}'
        }
        return headers


def get_sub_breeds(breed):
    res = requests.get(f'https://dog.ceo/api/breed/{breed}/list')
    return res.json().get('message', [])


def get_urls(breed, sub_breeds):
    url_images = []
    url = 'https://dog.ceo/api/breed/'
    if sub_breeds:
        for sub_breed in sub_breeds:
            res = requests.get(f"{url}{breed}/{sub_breed}/images/random")
            assert res.status_code == 200
            sub_breed_urls = res.json().get('message')
            url_images.append(sub_breed_urls)
    else:
        url_images.append(requests.get(f"{url}{breed}/images/random").json().get('message'))
    return url_images


@pytest.fixture(params=['doberman', 'bulldog', 'collie', 'greyhound'])
# @pytest.fixture(params=['collie'])
def setup(request):
    breed = request.param
    my_folder = f'test_folder_{breed}'
    sub_breeds = get_sub_breeds(breed)
    urls = get_urls(breed, sub_breeds)
    yandex_client = YaUploader()

    yandex_client.delete_folder(my_folder)  # удаляем папку перед тестом (не после потому что после может и не быть)
    yandex_client.create_folder(my_folder)
    for url in urls:
        part_name = url.split('/')
        name = '_'.join([part_name[-2], part_name[-1]])
        yandex_client.upload_photos_to_yd(my_folder, url, name)
    yield breed, sub_breeds, my_folder
    yandex_client.delete_folder(my_folder)


def test_upload_dog(setup):
    breed, sub_breeds, my_folder = setup
    # проверка
    yd = YaUploader()
    response = yd.get_folder(my_folder)
    assert response.status_code == 200
    assert response.json()['type'] == "dir"
    assert response.json()['name'] == my_folder
    items = response.json()['_embedded']['items']
    if not sub_breeds:
        assert len(items) == 1
        for item in items:
            assert item['type'] == 'file'
            assert item['name'].startswith(breed)

    else:
        assert len(items) == len(sub_breeds)
        for item in items:
            assert item['type'] == 'file'
            assert item['name'].startswith(breed)

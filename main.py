import os
import zlib
import tomllib
import subprocess
from PIL import Image


def parse_object(object_hash, description=None):
    """
    Извлечь информацию из git-объекта по его хэшу.
    """
    object_path = os.path.join(config['repo_path'], '.git', 'objects', object_hash[:2], object_hash[2:])
    with open(object_path, 'rb') as file:
        raw_object_content = zlib.decompress(file.read())
        header, raw_object_body = raw_object_content.split(b'\x00', maxsplit=1)
        object_type, content_size = header.decode().split(' ')
        object_dict = {}

        if object_type == 'commit':
            object_dict['label'] = r'commit_' + object_hash[:6]
            object_dict['children'] = parse_commit(raw_object_body)

        elif object_type == 'tree':
            object_dict['label'] = r'tree_' + object_hash[:6]
            object_dict['children'] = parse_tree(raw_object_body)

        elif object_type == 'blob':
            object_dict['label'] = r'blob_' + object_hash[:6]
            object_dict['children'] = []

        if description is not None:
            object_dict['label'] += r'_' + description

        object_dict['hash'] = object_hash
        return object_dict


def parse_tree(raw_content):
    """
    Парсим git-объект дерева.
    """
    children = []
    rest = raw_content
    while rest:
        mode, rest = rest.split(b' ', maxsplit=1)
        name, rest = rest.split(b'\x00', maxsplit=1)
        sha1, rest = rest[:20].hex(), rest[20:]
        children.append(parse_object(sha1, description=name.decode()))
    return children


def parse_commit(raw_content):
    """
    Парсим git-объект коммита.
    """
    content = raw_content.decode()
    content_lines = content.split('\n')
    commit_data = {'parents': []}

    commit_data['tree'] = content_lines[0].split()[1]
    content_lines = content_lines[1:]

    while content_lines[0].startswith('parent'):
        commit_data['parents'].append(content_lines[0].split()[1])
        content_lines = content_lines[1:]

    commit_data['message'] = '\n'.join(content_lines[1:]).strip()
    return [parse_object(commit_data['tree'])] + \
           [parse_object(parent) for parent in commit_data['parents']]


def contains_file_with_hash(tree_hash, target_hash):
    """
    Проверяет, содержит ли дерево файл с заданным хэшем.
    """
    tree = parse_object(tree_hash)
    for child in tree['children']:
        if child['hash'] == target_hash or contains_file_with_hash(child['hash'], target_hash):
            return True
    return False


def get_last_commit():
    """
    Получить хэш для последнего коммита в ветке.
    """
    head_path = os.path.join(config['repo_path'], '.git', 'refs', 'heads', config['branch'])
    with open(head_path, 'r') as file:
        return file.read().strip()


def generate_mermaid(filename):
    """
    Создать Mermaid-файл для графа зависимостей.
    """
    def recursive_write(tree):
        label = tree['label']
        children = tree['children']
        nodes = [f'{label} --> {child["label"]}' for child in children]
        return '\n'.join(nodes) + '\n'.join([recursive_write(child) for child in children])

    last_commit = get_last_commit()
    tree = parse_object(last_commit)
    graph = 'graph TD\n' + recursive_write(tree)

    with open(filename, 'w') as file:
        file.write(graph)


def visualize(graph_file, output_file):
    """
    Визуализировать граф с помощью Mermaid CLI.
    """
    subprocess.run([config['visualizer_path'], '-i', graph_file, '-o', output_file, '--scale', '3'])
    img = Image.open(output_file)
    img.show()


# Чтение конфигурации из TOML
with open('config.toml', 'rb') as f:
    config = tomllib.load(f)['config']

# Хэш целевого файла
target_file_hash = config['target_file_hash']

# Построение графа зависимостей
last_commit = get_last_commit()
if contains_file_with_hash(last_commit, target_file_hash):
    generate_mermaid('graph.mmd')
    visualize('graph.mmd', 'graph.png')
else:
    print("Целевой файл с указанным хэшем не найден в текущей ветке.")

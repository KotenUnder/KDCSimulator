import yaml
import KDCUtils

# YAML 設定ファイルを読み込む関数
def load_config(file_path):
    with open(file_path, 'r') as file:
        config = yaml.safe_load(file)
    return config


hole_1_1_data = load_config('KDC_course.yaml')['hole']
hole_1_1 = KDCUtils.HoleData(hole_1_1_data['size'][0], hole_1_1_data['size'][1],
                             hole_1_1_data['height'], hole_1_1_data['terrain'],
                             hole_1_1_data['bumper'], hole_1_1_data['object'])


if __name__ == "__main__":
    config = load_config('KDC_course.yaml') #ここはパスを適宜調整してください
    print()
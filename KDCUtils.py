import math
import KDCTables
import yaml
import json
from abc import ABC, abstractmethod

# 定数
HOLE_HEIGHT_1_LEVEL = 0x5A82
HOLE_HEIGHT_BUMPER = 0x2D41 # これ以上なら通過、未満で衝突

# 重力
GRAVITY_DEFAULT = -64
GRAVITY_TORNADO = -32
GRAVITY_NEEDLE = -96
GRAVITY_WHEEL = -112
GRAVITY_STONE = -128

# 初速ポテンシャル
POTENTIAL_VELOCITY_BURNING = 8000
POTENTIAL_VELOCITY_TORNADO = 3000

# 仰角
PITCH_DEFAULT = 60
PITCH_HIGHJUMP = 65

class HoleData:
    def __init__(self, width_x_: int, width_y_:int, height_table_: list, terrain_table_: list,
                 bumper_table_: list, object_table_: list):
        self._width_x = width_x_
        self._width_y = width_y_
        self._height_table = height_table_.copy()
        self._terrain_table = terrain_table_.copy()
        self._bumper_table = bumper_table_.copy()
        self._object_table = object_table_.copy()
        pass

    def _checkRange(self, x_: int, y_: int) -> bool:
        return (x_ >= 0) and (x_ < self._width_x) and (y_ >= 0) and (y_ < self._width_y)

    def getObject(self, x_: int, y_: int) -> int:
        # 範囲外ならオブジェクトなし
        if self._checkRange(x_, y_):
            return self._object_table[self._width_x * y_ + x_]
        else:
            return 0

    def getTerrain(self, x_: int, y_: int) -> int:
        # 範囲外ならオブジェクトなし
        if self._checkRange(x_, y_):
            return self._terrain_table[self._width_x * y_ + x_]
        else:
            return 0

    def getHeight(self, x_: int, y_: int) -> int:
        # 範囲外なら高さ0
        if self._checkRange(x_, y_):
            return self._height_table[self._width_x * y_ + x_]
        else:
            return 0

    def getBumper(self, block_x_: int, block_y_: int) -> list:
        # Y-方向、X+方向、Y+方向、X-方向の順に、バンパーの有無をbool listで返す
        if self._checkRange(block_x_, block_y_):
            value = self._bumper_table[self._width_x * block_y_ + block_x_]
            return [value ^ 1 == 1, value ^ 2 == 2, value ^ 4 == 4, value ^ 8 == 8]
        # 範囲外ならバンパーなし
        else:
            return [False, False, False, False]


def get_slopeId_from_terrainId(terrain_id_: int, inblock_id_: int) -> int:
    # 範囲チェック
    if terrain_id_ >= 0 and terrain_id_ <= 27 and inblock_id_ >= 0 and inblock_id_ <= 3:
        return KDCTables.KDC_slope_table[terrain_id_][inblock_id_]
    else:
        raise ValueError(f"terrain{terrain_id_} inblock{inblock_id_}")


def calculate_zoffset_partial(slope_id_: int, inblock_x_: int, inblock_y_: int) -> int:
    zoffset_index = 0

    # 最低点からの水平座標の差を求める。
    if slope_id_ == 0: # 傾斜ID=0 平坦の時 １段分の高さそのもの
        return HOLE_HEIGHT_1_LEVEL
    elif slope_id_ == 1: # 傾斜ID=1のとき
        zoffset_index = inblock_y_
    elif slope_id_ == 2:
        zoffset_index = 32767 - inblock_x_
    elif slope_id_ == 3:
        zoffset_index = 32767 - inblock_y_
    elif slope_id_ == 4:
        zoffset_index = inblock_x_

    # 斜面上Z座標テーブル用インデックスの計算
    zoffset_index = zoffset_index // 128

    return KDCTables.KDC_Zoffset_table[zoffset_index]


def calculate_zoffset_fullslope(terrain_id_: int, inblock_x_: int, inblock_y_: int) -> int:
    # ブロック内区分を求める
    inblock_id = calculate_inblock_id(inblock_x_, inblock_y_)
    # 対応する傾斜IDを求める
    slope_id = get_slopeId_from_terrainId(terrain_id_, inblock_id)

    # 基準点(最低点)からの床Z座標を求める
    zoffset = calculate_zoffset_partial(slope_id, inblock_x_, inblock_y_)

    # 地形ID16未満、つまり単純斜面のみである場合はzoffsetそのもの出力
    if terrain_id_ < 16:
        return zoffset % 0x10000
    # 基準点の高さを引く。この値はs16bitだが、のちに32bit扱いになるためu16と解釈される。
    else:
        return (zoffset - HOLE_HEIGHT_1_LEVEL) % 0x10000


def calculate_air_resistance(vx_: int, vy_: int) ->tuple:
    # 内部関数　空気抵抗を１変数について計算する。
    def calculate_air_resistance_single(v_: int):
        if v_ > 32767:
            v_ = v_ - 0x10000
        
        if v_ >= 0:
            return - ((v_ + 0x0080) // 0x0100)
        else:
            v_ = - v_
            return (v_ + 0x0080) // 0x0100

    # x, y成分それぞれ、内部関数を適用してtupleで返す。
    return (calculate_air_resistance_single(vx_),
            calculate_air_resistance_single(vy_))


class UShort:
    """
    A class to represent an unsigned short integer (0 to 65535).
    """

    def __init__(self, value: int):
        """
        Initializes the UShort instance with a given integer value.
        
        Parameters:
        value (int): The integer value to initialize the UShort instance.
        
        Raises:
        ValueError: If the value is not in the range 0 to 65535.
        """
        if not (0 <= value <= 65535):
            raise ValueError("Value must be between 0 and 65535.")
        self.value = value

    def __int__(self) -> int:
        """
        Returns the integer representation of the UShort instance.
        
        Returns:
        int: The integer value of the UShort instance.
        """
        return self.value


def get_potential_velocity(power_: int, is_flying_: bool, handicap_level_: int=0):
    HANDICAP_COEFFICIENT_LIST = [0x1300]
    if is_flying_:
        base_power = KDCTables.KDC_power_popup_table[power_]
    else:
        base_power = KDCTables.KDC_power_grounder_table[power_]

    return base_power * HANDICAP_COEFFICIENT_LIST[handicap_level_] // 0x4000



def calculate_initial_velocity(potential_: int, pitch_: int, yaw_: int):
    """
    ポテンシャル初速・仰角・方位角から初速(Vx, Vy, Vz)を計算する。
    """
    # Z速度と水平速度を確定させる
    v_z = multiple_32768(potential_, sine_kdc(pitch_))
    v_horizon = multiple_32768(potential_, cosine_kdc(pitch_))

    # 水平速度をx, y方向に分解する。この時、正負で誤差が出ないように０に近づける丸めにする
    v_x_32bit = v_horizon * cosine_kdc(yaw_)
    if v_x_32bit >= 0:
        v_x = v_x_32bit // 0x8000
    else:
        v_x = - (- v_x_32bit // 0x8000)

    v_y_32bit = v_horizon * sine_kdc(yaw_)
    if v_y_32bit >= 0:
        v_y = v_y_32bit // 0x8000
    else:
        v_y = - (- v_y_32bit // 0x8000)

    return (v_x, v_y, v_z)





def calculate_inblock_id(x_: int, y_: int)-> int:
    """
    ブロック内座標から、ブロック内区分を求める
    # 3 2
    # 0 1 という並び
    # 優先度は 1 > 0,2 > 3の順番
    Parameters:
    x_ (int): ブロック内X座標.
    y_ (int): ブロック内Y座標
    
    Returns:
    int: ブロック内区分
    """

    area_id = 0

    # X+Y >= 0x10000 (右上側)ならば、Y=1or2
    if (x_ + y_) >= 0x10000:
        area_id += 1
        # X < Y つまり右下側ならば、Y=2 そうでないならY=1のまま
        if x_ < y_:
            area_id += 1
    else:
        if (x_ - y_) < 0:
            area_id = 3
    
    return area_id

    


def multiple_32768(x_: int, y_: int) -> int:
    """
    Multiplies two integers and returns the result.
    
    Parameters:
    x_ (int): The first integer to multiply.
    y_ (int): The second integer to multiply.
    
    Returns:
    int: The product of x_ and y_.
    """
    return math.floor(x_ * y_ / 32768)


def round_off(x_: float) -> int:
    """
    四捨五入する。(銀行員のround to evenでなく、0.5は常に切り上げる)
    
    Parameters:
    x_ (float): The float to round off.
    
    Returns:
    int: The rounded integer.
    """
    return math.floor(x_ + 0.5)


def ground_info(kirby_info_: json, hole_info_: json) -> json:
    
    pass


def sine_kdc(angle_: int) -> int:
    """
    Computes the sine of a given angle and returns the result.
    
    Parameters:
    angle_ (int): The angle in degrees.
    
    Returns:
    int: The sine of the angle.
    """
    return KDCTables.KDC_sine_table[angle_ % 360]

def cosine_kdc(angle_: int) -> int:
    """
    Computes the cosine of a given angle and returns the result.
    
    Parameters:
    angle_ (int): The angle in degrees.
    
    Returns:
    int: The cosine of the angle.
    """
    return KDCTables.KDC_sine_table[(angle_ + 90) % 360]

def arctan_kdc(x_: int, y_: int) -> int:
    """
    Computes the arctangent of a given integer and returns the result.
    
    Parameters:
    x_ (int): The integer for which to compute the arctangent.
    y_ (int): The integer for which to compute the arctangent.
    
    Returns:
    int: The arctangent of x_. 0<=x<=359
    """
    # X, Yが0の時の処理
    if x_ == 0 and y_ == 0:
        return 0
    elif x_ == 0:
        return 90 if y_ > 0 else 270
    elif y_ == 0:
        return 0 if x_ > 0 else 180
    # |X| = |Y|の時の処理
    if x_ == y_:
        return 45 if x_ > 0 else 225
    elif x_ == -y_:
        return 315 if x_ > 0 else 135

    # 一般角の場合の処理
    absx = abs(x_)
    absy = abs(y_)
    # 小さい方を256倍して大きい方で割った時の商を求める
    if absx > absy:
        base_angle = 0 if x_ > 0 else 180
        ratio = (absy * 256) // absx
        angle_offset = KDCTables.KDC_arctan_table[ratio]
        # X, Y符号一致ならbaseに加える、逆ならbaseから引く 
        if x_ * y_ > 0:
            angle = base_angle + angle_offset
        else:
            angle = base_angle - angle_offset
    else:
        base_angle = 90 if y_ > 0 else 270
        ratio = (absx * 256) // absy
        angle_offset = KDCTables.KDC_arctan_table[ratio]
        # X, Y符号一致ならbaseから引く、逆ならbaseに加える
        if x_ * y_ > 0:
            angle = base_angle - angle_offset
        else:
            angle = base_angle + angle_offset

    # angleを0-359の範囲に収める
    return angle % 360




def calculate_friction(friction_coefficient_: int, movement_angle_: int) -> int:
    # X, Y方向それぞれの摩擦力を返す
    cosine_value = cosine_kdc(movement_angle_)
    sine_value = sine_kdc(movement_angle_)

    # 0以上の時：+128して切り捨て、負の時：-128して切り捨て
    if cosine_value >= 0:
        friction_x = (multiple_32768(friction_coefficient_, cosine_value) + 128) // 256
    else:
        friction_x = (multiple_32768(friction_coefficient_, cosine_value) - 128) // 256
    if sine_value >= 0:
        friction_y = (multiple_32768(friction_coefficient_, sine_value) + 128) // 256
    else:
        friction_y = (multiple_32768(friction_coefficient_, sine_value) - 128) // 256
    
    return (- friction_x, - friction_y)




def hex_to_int(hex_str: str) -> int:
    """
    Converts a hexadecimal string to an integer.
    
    Parameters:
    hex_str (str): The hexadecimal string to convert.
    
    Returns:
    int: The integer representation of the hexadecimal string.
    """
    bit_length = len(hex_str) * 4
    # 10進数の整数に変換
    int_val = int(hex_str, 16)
    # 最上位ビットが立っているか判定（負の数かどうか）
    if int_val & (1 << (bit_length - 1)):
        int_val -= 1 << bit_length
    return int_val


class BumperObstacle:
    @abstractmethod
    def discriminate(self, inblock_x_: int, inblock_y_: int) -> bool:
        pass

    def detect_collision(self, inblock_x1_: int, inblock_y1: int, inblock_x2_: int, inblock_y2_: int, z_diff_: int=0) -> bool:
        # 領域が前後共に0or1で衝突なし、変化ありで衝突有
        return (self.discriminate(inblock_x1_, inblock_y1) ^ self.discriminate(inblock_x2_, inblock_y2_)) == 1 and z_diff_ < HOLE_HEIGHT_BUMPER


# カービィの状態
class KirbyState:
    def __init__(self):
        # メンバー変数
        # 座標
        self.c_x = 0
        self.c_y = 0
        self.c_z = 0
        # 速度
        self.v_x = 0
        self.v_y = 0
        self.v_z = 0
        # 角度
        self.yaw = 0
        # フライ状態かどうか
        self.is_flying = False
        # 重力
        self.gravity = GRAVITY_DEFAULT
        # コピー能力関連
        # コピー使用可能状態か
        self.ability_is_prepared = False
        # 準備されているコピー能力の種類
        self.ability_prepared_id = 0
        # 現在使用されているコピー能力
        self.ability_used_id = 0
        self.ability_counter = 0 # フレーム数カウンター
        self.ability_freespace1 = 0 # 自由領域、コピー能力によって用途が異なる。
        self.ability_freespace2 = 0
        self.ability_freespace3 = 0
        self.ability_freespace4 = 0
        




if __name__ == "__main__":
    shot = get_potential_velocity(60, False)
    init = calculate_initial_velocity(shot, 0, 315)
    # Example usage
    mx = 0x20CC
    my = 0x5506
    mz = hex_to_int("BA66")
    vx = hex_to_int("FF02")
    vy = 0x0896
    vz = hex_to_int("FAEE")
    """
    # 衝突サンプル
    mx = hex_to_int("B7D0")
    my = hex_to_int("EB04")
    mz = 0
    vx = 0x09AA
    vy = 0x09AA
    vz = 0
    """
    theta_yz = arctan_kdc(mz, my)
    sine_theta_yz = sine_kdc(theta_yz)
    cosine_theta_yz = cosine_kdc(theta_yz)

    # 斜辺TBの長さを計算する
    tb_y = multiple_32768(my, sine_theta_yz) if my >= 0 else -multiple_32768(-my, sine_theta_yz)
    tb_z = multiple_32768(mz, cosine_theta_yz) if mz >= 0 else -multiple_32768(-mz, cosine_theta_yz)
    tb_len = tb_y + tb_z

    # 三角形TBOでθx'(角BTO)を求める
    theta_x1 = arctan_kdc(tb_len, mx)
    sine_theta_x1 = sine_kdc(theta_x1)
    cosine_theta_x1 = cosine_kdc(theta_x1)

    # 正規化法線ベクトルN(nx, ny, nz)を計算する
    nx = sine_theta_x1
    ny = multiple_32768(cosine_theta_x1, sine_theta_yz) if cosine_theta_yz >= 0 else -multiple_32768(cosine_theta_x1, -sine_theta_yz)
    nz = multiple_32768(cosine_theta_x1, cosine_theta_yz) if cosine_theta_yz >= 0 else -multiple_32768(cosine_theta_x1, -cosine_theta_yz)

    # 内積k = N・vを計算する
    nvx = multiple_32768(nx, vx) if vx >= 0 else -multiple_32768(nx, -vx)
    nvy = multiple_32768(ny, vy) if vy >= 0 else -multiple_32768(ny, -vy)
    nvz = multiple_32768(nz, vz) if vz >= 0 else -multiple_32768(nz, -vz)

    k = nvx + nvy + nvz

    # k N (=速度の法線方向成分)を計算する
    if k >= 0:
        rx = multiple_32768(k, nx)
        ry = multiple_32768(k, ny)
        rz = multiple_32768(k, nz)
    else:
        rx = -multiple_32768(-k, nx)
        ry = -multiple_32768(-k, ny)
        rz = -multiple_32768(-k, nz)

    # 正規化接線ベクトルT(tx, ty, tz)を計算する

    print()

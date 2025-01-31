import json
import time

import httpx
import datetime

import okx.TradingData as TradingData
import okx.Account as Account
import okx.Trade as Trade
import okx.PublicData as PublicData

# 模拟盘apikey
demo_api_key = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxx"
demo_api_secret_key = "XXXXXXXXXXXX"
demo_passphrase = "你设置的密码"
# 实盘apikey 必填，因为查询交易大数据必须使用实盘的API，模拟盘的API没有这个权限
live_api_key = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxx"
live_api_secret_key = "XXXXXXXXXXXX"
live_passphrase = "你设置的密码"

# live trading: 0, demo trading: 1 实盘0，模拟盘1
# flag的双引号不能省略哦
flag = "0"

# 0: post only 只挂单, 1: market 直接市价成交
fast_trade_mode = 0
# 交易对代码
INST_ID = "BTC-USDT-SWAP"
# 1.0 BTC代表的张数，okx的BTC合约是0.01BTC一张
btc_per_zhang = 100
# 每周期后的等待时间（秒）
wait_time = 5

# 最小调整单位数量（单位是最小允许交易数量，就okx的BTC合约而言是0.0001BTC，0.01张）
# 此处10代表调整数量小于0.001BTC不调整
min_adjust_num = 10
# 最小调整比例 0.1代表调整比例小于10%时不调整，比如现在持有1BTC，只调整到1.09BTC，不调整
min_adjust_ratio = 0.1

# 暂停脚本与检测脚本是否还在运行的测试交易对名
# 1 若此交易对的杠杆被手动设置成了1.0，则脚本会暂停运行
# 2 若此交易对的杠杆不为1.0，则脚本会修改为10.0，可以通过修改此交易对的杠杆来检测脚本是否还在运行
KEEP_ALIVE_INST_ID = "AAVE-USDT-SWAP"

if flag == "0":
    api_key = live_api_key
    api_secret_key = live_api_secret_key
    passphrase = live_passphrase
else:
    api_key = demo_api_key
    api_secret_key = demo_api_secret_key
    passphrase = demo_passphrase

accountAPI = Account.AccountAPI(api_key, api_secret_key, passphrase, False, flag)
tradeAPI = Trade.TradeAPI(api_key, api_secret_key, passphrase, False, flag)
# 查询交易大数据必须使用实盘的API
publicAPI = PublicData.PublicAPI(live_api_key,
                                 live_api_secret_key, live_passphrase,
                                 use_server_time=False,
                                 flag="0")
TradingDataAPI = TradingData.TradingDataAPI(live_api_key,
                                            live_api_secret_key, live_passphrase,
                                            use_server_time=False,
                                            flag="0")

last_radio = None
last_time = 0
# 不再使用，以账户内设置的杠杆为准
lever = 0


def get_now_radio():
    """
    获取当前最新多空比例
    :return: float(多空比例)
    """
    global last_radio, last_time
    r = TradingDataAPI.get(
        url="/api/v5/rubik/stat/contracts/long-short-account-ratio-contract-top-trader",
        params={
            "instId": INST_ID
        }
    )
    json_data = json.loads(r.content.decode("utf-8"))
    get_ratio = float(json_data["data"][0][1])
    get_time = int(json_data["data"][0][0])
    if get_time > last_time:
        last_radio = get_ratio
        last_time = get_time
    return last_radio


def get_usdt_remain_eq():
    """
    获取当前账户交易USDT权益
    :return: float(USDT权益)
    """

    time.sleep(0.5)

    r = accountAPI.get_account_balance("USDT")
    usdt_details = r["data"][0]["details"][0]
    return float(usdt_details["eq"])


def cal_leverage(ratio):
    """
    根据多空比例计算杠杆
    :param ratio: 多空比例
    :return: 杠杆大小，负数为做空 float(杠杆)
    """
    if ratio < 1:
        buy = 1.0
        sell = buy / ratio
    else:
        sell = 1.0
        buy = sell * ratio
    k = buy - sell
    # control the risk 杠杆上限
    if k > 0.5:
        k = 0.5
    if k < -0.5:
        k = -0.5
    return k


def cal_trading_num(now_ratio, remain_usdt, now_btc_price):
    """
    根据多空比例计算需要交易的BTC数量
    :return: float 要交易的BTC数量
    """
    k = cal_leverage(now_ratio)
    need = float(k * remain_usdt * lever / now_btc_price)
    return need


def get_now_position():
    """
    获取当前持仓
    :return: float(持仓数量)
    """
    result = accountAPI.get_positions()
    all_pos = result["data"]
    pos = {}
    for i_pos in all_pos:
        if i_pos["instId"] == INST_ID:
            pos = i_pos
    if not bool(pos):
        pos_num = 0
    elif pos["posSide"] != "net":
        raise Exception("not in 'net' mode, 确保持仓模式为单向持仓")
    else:
        pos_num = float(pos['pos']) / btc_per_zhang
    return pos_num


def get_mark_price():
    """
    获取标记价格
    :return: float(标记价格)
    """
    r = publicAPI.get_mark_price(instType="SWAP", instId=INST_ID)
    return float(r['data'][0]['markPx'])


def trade_btc_in_market(btc_num: float):
    """
    直接进行市价交易
    :param btc_num: 交易的BTC数量
    :return: None
    """
    zhang = float(btc_num * btc_per_zhang)
    if zhang < 0:
        side = "sell"
    else:
        side = "buy"
    result = tradeAPI.place_order(
        instId=INST_ID,
        tdMode="cross",
        side=side,
        posSide="net",
        ordType="market",
        sz="%.2f" % (abs(zhang))
    )
    if result['code'] != '0':
        msg = result['data'][0]['sMsg']
        print(msg)
    else:
        print("trade done,at %.4f btc" % btc_num)


def trade_btc_in_post_only(btc_num: float):
    """
    只挂单交易
    若挂单失败(canceled)，价格差值增加1
    若无人接单(live)，价格差值减少0.2
    :param btc_num: 交易的BTC数量
    :return: None
    """
    zhang = float(btc_num * btc_per_zhang)
    remain_zhang = zhang
    if zhang < 0:
        side = "sell"
    else:
        side = "buy"

    # 挂单价格与当前价格的差值
    cha = 10

    # try 10 times,limit at -10 or +10 if failed, retry
    for i in range(10):
        now_mark_price = get_mark_price()
        if side == "buy":
            order_price = now_mark_price - cha
        else:
            order_price = now_mark_price + cha
        result = tradeAPI.place_order(
            instId=INST_ID,
            tdMode="cross",
            side=side,
            posSide="net",
            ordType="post_only",
            px="%.1f" % order_price,
            sz="%.2f" % (abs(remain_zhang))
        )
        ord_id = result['data'][0]['ordId']
        time.sleep(0.5)
        for j in range(10):
            order_info_result = tradeAPI.get_order(
                instId=INST_ID,
                ordId=ord_id
            )
            order_status = order_info_result['data'][0]['state']
            if order_status == "filled":
                print("D")
                print("trade done,at %.4f btc" % btc_num)
                return
            elif order_status == "live":
                time.sleep(1)
                cha -= 0.2
                print("L", end="")
            elif order_status == "canceled":
                print("C", end="")
                cha += 1
                break
            elif order_status == "partially_filled":
                time.sleep(1)
                print("P", end="")
            else:
                raise Exception("unknown order status")
        # cancel order
        tradeAPI.cancel_order(
            instId=INST_ID,
            ordId=ord_id
        )
        # get filled num
        order_info_result = tradeAPI.get_order(
            instId=INST_ID,
            ordId=ord_id
        )
        filled_num = float(order_info_result['data'][0]['accFillSz'])
        remain_zhang = remain_zhang - filled_num
        if abs(remain_zhang) < 0.01:
            print("trade done,at %.4f btc" % btc_num)
            return
        print("R")
    print("Trade Failed, Try Next Time" % btc_num)


def adjust_pos(now_pos, need):
    """
    调整持仓，执行交易
    :param now_pos: 当前持仓
    :param need: 需要调整到的持仓
    :return:
    """
    trade_num = need - now_pos
    if abs(int((trade_num * btc_per_zhang) * 100)) <= min_adjust_num or abs(trade_num) < abs(
            now_pos) * min_adjust_ratio:
        print("adjust num is %f,no need to adjust" % (trade_num * btc_per_zhang))
        return 0
    if fast_trade_mode == 0:
        trade_btc_in_post_only(trade_num)
    else:
        trade_btc_in_market(trade_num)
    return "%.4f" % trade_num


def clean_btc_pos():
    """
    清空持仓
    :return: None
    """
    pos = get_now_position()
    if pos == 0:
        return
    if fast_trade_mode == 0:
        trade_btc_in_post_only(-pos)
    else:
        trade_btc_in_market(-pos)


def main():
    global lever
    while 1:
        try:
            alive = get_leverage_info(KEEP_ALIVE_INST_ID)
            # AAVE-SWAP is the token of the exchange, if it isn't equal 1, we can continue
            if alive == 1.0:
                time.sleep(5)
                continue
            else:
                set_leverage(KEEP_ALIVE_INST_ID, 10.0)

            now_leverage = get_leverage_info(INST_ID)
            lever = now_leverage

            print('===============BEGIN==================')
            btc_mark_price = get_mark_price()
            usdt_remain = get_usdt_remain_eq()
            now_radio = get_now_radio()
            lev_info = cal_leverage(now_radio)

            if 0.01 < abs(lev_info) < 0.03:
                print("ratio not clear, at %.2f do nothing" % abs(lev_info))
                continue
            elif abs(lev_info) <= 0.01:
                print("ratio is too small, at %.2f, clean pos" % abs(lev_info))
                clean_btc_pos()
                continue

            print("btc market price is %f, now we have %f USDT, radio of top is %f" % (
                btc_mark_price, usdt_remain, now_radio))

            now_pos = get_now_position()
            print("now we have %f btc" % now_pos)

            need_to_at = cal_trading_num(now_radio, usdt_remain, btc_mark_price)
            print('we need to be in %f' % need_to_at)

            adjust = adjust_pos(now_pos, need_to_at)
            nowtime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print('================END===================')
            time.sleep(wait_time)
        except httpx.ConnectTimeout or ConnectionError as Ee:
            print(f"Net work error")
            continue
        except Exception as e2:
            print(f"An error occurred: {e2}")
            continue


def get_leverage_info(instId):
    """
    获取杠杆大小
    :param instId: 交易对名
    :return: float(杠杆)
    """
    while 1:
        try:
            r = accountAPI.get_leverage(instId=instId, mgnMode="cross")
            return float(r['data'][0]['lever'])
        except httpx.ConnectTimeout as Ee:
            continue
        except Exception as e:
            print(e)
            assert False


def set_leverage(instId, s_lever):
    """
    设置杠杆
    :param instId: 交易对名
    :param s_lever: 杠杆大小
    :return: None
    """
    while 1:
        try:
            r = accountAPI.set_leverage(instId=instId, mgnMode="cross", lever=s_lever)
            return r
        except httpx.ConnectTimeout as Ee:
            continue
        except Exception as e:
            print(e)
            assert False


if __name__ == '__main__':
    main()

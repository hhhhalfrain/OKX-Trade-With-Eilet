## 这是什么

这是一个在OKX欧易平台上自动交易的Python脚本。脚本完全开源，但这也意味着我不会对您的资产损失负责，希望您运行代码前知道自己在做什么。

## 脚本运行逻辑

**读取当前OKX持仓量前5%的用户BTC合约持仓多空比情况（精英账户多空比Top.Acc L/S），然后跟他们的方向按持仓比例开单并监控调整**

用一个简单的例子来解释运作流程：

当精英账户多空比为1.2，则多空数量差值为 1.2 - 1 = 0.2，脚本会自动使用20%的仓位，并读取平台内设置的BTC杠杆倍数开仓。假设当前交易账户内有10000USDT，BTC标记价格为100000USDT，杠杆倍数为10倍，则脚本会拿出20%的仓位，即2000USDT以10倍杠杆开多，相当于买入0.2BTC看多合约。

为了节约手续费，交易时默认采用高级限价委托的”只挂单“模式。默认起始差值为10，就本例子而言，买入时会以99990的价格挂单，若10秒内无法成交，则会减2差值，以99992的价格挂单，若挂单后因为价格波动成为吃单的一方，则会取消订单，加1差值，以此类推直到成交为止。（挂单手续费只有万分之二，是吃单的2/5）

假设过了一段时间，精英持仓多空比变成了0.8，计算多空数量差值为 1 - 1/0.8 = - 0.25 则脚本会出售掉之前的看多合约，再拿出25%的仓位做空，也就是卖出0.45BTC以达到对应仓位

假设当前多空数量差值的绝对值小于0.03，说明市场情况还不明朗，会停止执行策略（但不平现有的仓位）并等待机会，当多空数量差值的绝对值小于0.01，才会平掉现有仓位。

## 如何部署

### 安装运行环境

安装python3 版本>=3.9

安装必备运行库 python-okx

```
pip install python-okx
```

### 申请API

在模拟盘和实盘各申请一个交易API，权限勾选”读取“和”交易“，获取API KEY

请保管好您的API信息，这相当于你的账号的密码

然后将获取到的API填入代码中的api_key等字段中

### 修改自定义参数

主要是要修改这三个参数，按需修改就行。注意flag参数的双引号不能省

```python
# live trading: 0, demo trading: 1 实盘0，模拟盘1
flag = "0"
# ......
# 最小调整单位数量（单位是最小允许交易数量，就okx的BTC合约而言是0.0001BTC，0.01张）
# 此处10代表调整数量小于0.001BTC不调整
min_adjust_num = 10
# 最小调整比例 0.1代表调整比例小于10%时不调整，比如现在持有1BTC，只调整到1.09BTC，不调整
min_adjust_ratio = 0.1
```



### 第一次启动脚本前要做的检查单

1. 确保BTC-USDT永续合约处于全仓模式下
2. 确保AAVE-USDT永续合约处于全仓模式下
3. 确保交易模式处于单向持仓模式（合约界面-右上角三个点-交易设置-仓位模式-单向持仓）
4. 确保BTC-USDT永续合约没有挂单和持仓
5. 确保平台上设置的BTC杠杆大小是您所期望的
6. 确保AAVE-USDT的杠杆大小不为1也不为10
7. 隔离不想投入的USDT到资金账户中，以免被脚本用来开仓
8. 中国大陆无法访问API接口，需要科学上网

### 推荐的初始配置

经过测试，5倍或者10倍杠杆可能是不错的选择，虽然10倍杠杆看起来大，但这周以来多空数量差绝对值最高也就0.3，10倍杠杆也就只是3倍实际杠杆，并且脚本会自动稳定实际杠杆，当杠杆不符合预期时会自动减仓, 不必担心起床看到归零。

## 方便地控制脚本

考虑到脚本部署在电脑，外出时只能使用手机，不方便临时暂停脚本或者检查脚本是否有在运行，这里用AAVE合约杠杆倍数作为标志物

1 若此交易对的杠杆被手动设置成了1.0，则脚本会暂停运行

2 若此交易对的杠杆不为1.0，则脚本会修改为10.0，可以通过修改此交易对的杠杆来检测脚本是否还在运行。比如手动设置为5，如果很快杠杆被修改为10了说明脚本还在运行

可以通过修改自定义参数中的KEEP_ALIVE_INST_ID改变测试交易对

（原本想用COOKIE-USDT交易对作为测试交易对的，结果模拟盘没有，测试的时候会报错。所以就选择了一个比较好找又比较冷门的交易对）

## 其他
如果觉得好用请给我一个Star吧，谢谢！
将来会写RSI指标和MACD指标的策略，敬请期待
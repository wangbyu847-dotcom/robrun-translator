# ROB RUN 实时屏幕翻译工具（免费版）v3 离线版

做这个小工具就一个想法：让中文玩家玩 ROB RUN 的时候顺畅一点，不用对着满屏英文干瞪眼。

也是为了不想给加速器充钱的同胞们做的——加速器自带的翻译功能要花钱，这个免费。

> 给 Steam 游戏 ROB RUN 用的实时翻译小工具：游戏画面上的英文会被自动认出来、翻成中文，再浮在原来的位置上，看起来就像游戏自带中文一样。
>
> **v3 新功能：在线/离线两种翻译引擎，可切换。** 在线用免费接口（翻得准，要联网）；离线用 Argos 本地模型（断网也能翻，不会被限流）。按 **F10** 切换，在线接口报错时自动回落到离线。

## 在 Windows 上实测过吗？

说实话，没有。作者这边没有 Windows 环境，悬浮窗能不能稳稳盖在游戏上、全屏独占模式下表现怎么样，这些都没法实测，都是按文档和原理写的，Linux 上只验证了截屏、认字、翻译这条链路。

所以如果你在 Windows 上玩 ROB RUN，欢迎下载下来试试，帮我看看实际用起来怎么样。遇到问题别客气，直接到 GitHub Issues 说一声，写清楚这几样就行：Windows 版本、游戏开的哪种窗口模式（无边框还是全屏独占）、报错截图，或者黑窗口里那段报错信息。能复现的问题，我尽量修。

## 它安全吗？会封号吗？

**不会。** 它的原理和 LagoFast、UU 加速器自带的翻译功能完全一样：

```
截屏 → OCR 认字 → 机器翻译 → 悬浮窗显示
```

全程只"看"你的屏幕，不改游戏文件、不往游戏里塞东西、不读游戏内存。ROB RUN 的反作弊（Easy Anti-Cheat）只拦改游戏的东西，这种只看屏幕的工具它不管，和 Discord 悬浮窗、OBS 直播一个性质。

## 准备工作（只做一次）

### 第 1 步：安装 Python

1. 打开 https://www.python.org/downloads/
2. 点那个黄色的 **Download Python** 按钮，下载安装包
3. 打开安装包，**最重要的一步**：把底部的 **"Add Python to PATH"** 打上勾，再点 Install
4. 装完后按 `Win + R`，输入 `cmd` 回车，输入 `python --version` 回车
   - 如果显示 `Python 3.11.x` 之类的版本号，就是装好了
   - 如果显示"不是内部命令"，就是第 3 步的勾没打上，卸载重装一次，记得打勾

### 第 2 步：准备好这份工具

把 `robrun-translator` 整个文件夹放到你想放的地方就行，比如桌面。
文件夹里应该有这几个文件：

| 文件 | 是干什么的 |
|---|---|
| `start.bat` | 双击它就能用（一键启动，在线模式） |
| `start-offline.bat` | 双击它就用离线模式启动（断网也能翻） |
| `robrun_translator.py` | 翻译工具本体 |
| `user_corrections.txt` | **你的纠错本**：发现翻错了，在这里加一行就行（见下面） |
| `requirements.txt` | 需要安装的免费库清单（在线模式） |
| `requirements-offline.txt` | 离线引擎依赖清单（轻量版：ctranslate2 + sentencepiece，直接加载 Argos 模型，不需要 torch） |
| `requirements-offline-full.txt` | 离线引擎完整版依赖（可选：Argos 官方库，会额外下载 500MB+ 的 torch，网不好时可能失败——失败不影响使用，轻量版照样能翻） |
| `README.md` | 就是这份说明 |
| `all-game-text-zh-en.md` | 从实机视频里收割的游戏文本中英对照表，供查阅 |

## 怎么用

1. **双击 `start.bat`**，会弹出一个黑窗口，自动检查 Python、自动装依赖
   - 第一次运行要下载 OCR 模型（十几 MB），多等一会儿是正常的
   - 装好后黑窗口会显示"正在启动翻译工具"，**这个黑窗口不要关**
   - 想直接用离线模式启动，就双击 **`start-offline.bat`**
2. **打开 ROB RUN，进游戏之前先把游戏设成"无边框窗口"模式**
   - 游戏设置 → 画面/显示 → 窗口模式 → 选"无边框"或"窗口化全屏"
   - 全屏独占模式下悬浮窗可能盖不上去，这是 Windows 的限制，不是工具坏了
3. 进游戏，画面上的英文旁边就会浮出中文翻译
   - 翻译大约每秒刷新一次
   - 按 **F9** 可以开关翻译（黑窗口里会提示"翻译已开启/已暂停"，暂停时悬浮窗上的旧译文会清掉）
   - 按 **F10** 可以切换在线/离线引擎（见下面"在线还是离线"）
   - 不想用了就关掉黑窗口，或者在黑窗口里按 `Ctrl+C`

## 在线还是离线？（v3 新功能）

工具里有两种翻译引擎，默认用在线，随时可以换：

|  | 在线引擎（默认） | 离线引擎 |
|---|---|---|
| 怎么翻 | MyMemory 免费接口主用，Google 备用 | Argos Translate 本地模型，在你电脑上跑 |
| 要联网吗 | 要 | 第一次下载模型要联网，之后**断网也能用** |
| 翻译质量 | 比较好，游戏黑话、整句上下文翻得比较准 | 差一截：小模型，单个词、缩写、游戏黑话容易翻错，翻错了就加一行纠错（见下面） |
| 速度 | 看网速，一般几百毫秒 | 亚秒级（模型已加载进内存后，一句短句一般不到 1 秒；首次加载模型不到 1 秒。内存：轻量加载实测约 120MB，官方库完整版约 200–500MB） |
| 会被限流吗 | 有可能（免费接口用多了会报 429） | 不会 |

**三种切换方式：**

1. **启动时指定**：双击 `start-offline.bat`，就是离线模式启动；双击 `start.bat`，就是在线模式启动。
2. **运行中按 F10**：在线、离线来回切，黑窗口会打印当前用的哪个引擎，悬浮窗左上角也会显示一行小字（"在线·MyMemory/Google"或"离线·Argos"）。
3. **自动回落**：在线模式下如果接口报错（429 限流、断网），工具会自动切到离线引擎再翻一次，并打印提示。切过去之后会一直待在离线，直到你按 F10 切回在线（或重启）。

**第一次用离线模式：** 工具会联网下载一次英中模型（约 70MB），多等一会儿；下载完存在你电脑上，以后断网也能用。模型下载失败也不影响在线模式。

**实话实说：** 离线模型翻游戏文本确实不如在线。实测 89 行里，离线翻得好的有 `GOODS`→货物、`Drill`→钻探、`ID Card`→身份证、`SUSPICIOUS DOOR`→特别的门、`Looty Bay`→卢蒂湾；翻坏的也不少：`BAG`→银行、`LENNY`（人名）→伦敦、`STEAKHOUSE`→楼梯、`DEPOSIT BOX`→设计包、`1MILLIONDEBT`→1毫米重联，而且 `FPS:186 PING:93MS` 这种带数字的行它翻不出来，还会多带一个"(英语)."的尾巴。离线是"不断线"的备胎，不是"翻得更好"的升级；有网的时候还是在线优先，断网或被限流时离线顶上。翻错了就往 `user_corrections.txt` 里加一行，离线也会越用越准。

## 自适应翻译是怎么工作的（v2 新版）

老版本是"先查一个 35 词的字典，查不到再机翻"——单个词没上下文，机翻经常翻错（比如 PLAY 翻成"玩耍"，INVENTORY 翻成"递延支出"）。新版改成自适应翻译，不靠大字典了，按这个顺序工作：

1. **你的纠错优先**：`user_corrections.txt` 里你写的条目，优先级最高，直接覆盖机翻结果。
2. **整段带上下文机翻**：同一屏上相邻的几行字会拼成一段一起发给翻译接口，引擎按上下文选词。比如抢劫语境下的 "Rob the bank and escape with the loot"，会翻成"抢劫银行并带着赃物逃跑"，而不会把 Rob 翻成"机器人"。
3. **专有名词修正**：机翻之后，只修正那些实测一定会翻错的专有名词（比如"洗衣台"改回"洗钱桌"、"影子总督"改回"影子州长"），这是拿真机翻结果一条一条测出来的。

## 发现翻错了怎么办？——加一行纠错就行

这就是"自适应学习"：工具会越用越准，因为你教它。

1. 用记事本打开 `user_corrections.txt`
2. 按这个格式加一行：`英文原文 = 中文翻译`
   - 比如：`Rob the bank = 抢银行`
   - 比如：`Dirty Cash = 黑钱`
3. 保存，**不用重启工具**，文件改了会自动重新读取，下一秒刷新就生效
4. 不想要了就把那行删掉，同样不用重启

文件里已经自带了 7 条起步纠错（PLAY、INVENTORY、RESUME、SELL、BUY、CONTROLS、SETTINGS），都是实测机翻一定会翻错的词，不喜欢可以直接改。

## 只想翻屏幕的一块区域？

默认是全屏翻译。如果你只想翻某一块（比如只翻任务栏）：

1. 用记事本打开 `robrun_translator.py`
2. 找到 `REGION = None` 这一行，改成比如 `REGION = (0, 0, 960, 540)`
   - 四个数字是：左上角 x、左上角 y、宽、高（单位是像素）
3. 保存，双击 `start.bat` 重新运行

## 常见问题

**Q：双击 start.bat 提示"没有找到 Python"？**
A：Python 没装好，或者安装时没勾 "Add Python to PATH"。按上面"第 1 步"重装一次，记得打勾。

**Q：安装依赖特别慢 / 报错？**
A：start.bat 会自动换国内镜像再试一次。如果还是失败，检查一下网络，或者打开 cmd 手动运行：
`pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple`

**Q：黑窗口显示"翻译失败"，画面上没有中文？**
A：在线接口可能暂时连不上或被限流。v3 会自动切到离线引擎再翻一次（黑窗口会打印"已自动切换到离线引擎"），等一会儿就有中文了。如果离线也没装好（第一次用离线要联网下载模型），就先确认电脑能上网，过会儿再试；也可以按 F10 手动切回在线再试。

**Q：离线模式怎么开？要下载什么？**
A：三种办法：双击 `start-offline.bat`；或运行中按 F10；或在线失败时自动切过去。第一次用离线模式要联网下载一次英中模型（约 70MB），之后断网也能用。模型占内存实测约 120MB（轻量加载），翻译是亚秒级，不是"0 毫秒"。

**Q：离线翻得准吗？**
A：不如在线。离线是小模型，游戏黑话、单个词、缩写容易翻错，整句带上下文的会好一些。实测里 `BAG`→银行、`LENNY`→伦敦、`STEAKHOUSE`→楼梯都是离线翻坏的，`FPS:186 PING:93MS` 这种行它翻不出来还多带"(英语)."。翻错了就往 `user_corrections.txt` 里加一行纠错，离线也会越用越准。有网的时候建议用在线，断网或被限流时离线顶上。

**Q：悬浮窗看不见中文？**
A：先确认三件事：① 游戏是不是"无边框窗口"模式；② 黑窗口有没有报错；③ 按一下 F9，可能是翻译被暂停了。还不行就试试右键 start.bat →"以管理员身份运行"。

**Q：有些词翻错了 / 认错了？**
A：先看是不是专有名词或游戏黑话——这种在 `user_corrections.txt` 里加一行纠错是最快的办法（见上面"发现翻错了怎么办"）。如果是 OCR 把字认错了（比如把 0 认成 O），把游戏里的界面缩放调大一点会好很多。

**Q：玩游戏会变卡吗？**
A：基本不会。翻译每秒才做一次，而且同一句话只翻一次就记住了，CPU 占用很小。

**Q：能翻聊天框里别的玩家说的话吗？**
A：能，聊天框里的英文一样会被认出来翻译。不过玩家打字经常有缩写和错别字，翻出来可能不太准。

## 卸载

直接把整个 `robrun-translator` 文件夹删掉就行，不留任何东西。

## 实测数据（2026-11-16/17，Linux 虚拟机）

- **收割**：3 个 YouTube 实机视频（新手入门 13:48、银行金库抢劫 7:24、单人赚钱 21:40），抽帧 850 帧，OCR 原始收割 2236 条英文文本，归一化去重后 1780 条，过滤乱码后 1527 条，加上攻略站标准术语 63 条，**对照表共 1590 条**（`all-game-text-zh-en.md`，分 11 类）。
- **新旧对比（v2）**：抽 24 组同屏共 89 行真实游戏文本，新版明显更好约 20 行（`Drill` 从"全民演习"变成"钻孔机"、`GOODS` 从"家电"变成"货物"、`Yourhomebase` 从"您的主页"变成"你的大本营"），旧版更好 1 行（新版把玩家名 Deaf Rat 翻成了"聋鼠"），其余相当或都翻不出来。完整的逐行对比表没放进仓库，这里只写结论。
- **在线 vs 离线对比（v3，2026-11-17 实测）**：同一批 89 行真实游戏文本，两种引擎各翻一遍，逐行对比的结果也没放进仓库，结论是：离线 89/89 行成功，总用时 10.1 秒（不含模型加载），每组中位数 0.40 秒、最慢 0.77 秒，模型首次加载+翻译 0.7 秒，内存增量实测约 120MB，单句平均约 55 毫秒。注意：本次实测时两个在线接口（MyMemory、Google）都被限流 429，89 行只成功 1 行、耗时 398.4 秒——这就是离线回落存在的意义。**断网启动验证**：把所有联网入口都堵死后，已装好的离线模型照常加载、零联网调用，`Rob the bank`→抢银行。**工作线程验证**：无显示器环境下跑真实主循环 30 秒，截屏→OCR→翻译→悬浮窗跑了 16 轮，60 条中文译文送到悬浮窗，线程存活、没闪退，每次截屏前都先隐藏了悬浮窗。**引擎切换验证**：`--offline` 启动、F10 切换、在线全失败（模拟 429）自动回落离线，全部通过。这 11 项检查全都通过了，都是在 Linux 虚拟机上跑的，Windows 下还没条件跑。
- **2026-11-20 改完几个小问题后又复测了一轮（还是 Linux 虚拟机）**：导入没问题；OCR 样例图 5 行全认出来了；离线翻译 5/5 行都翻出来了；主循环跑了 35 秒、20 轮截屏→认字→翻译→悬浮窗，没闪退，暂停时悬浮窗确实清掉了；纠错文件改完下一秒就生效，删掉就回落回机翻。在线接口这次又被限流 429（和 11-17 那次一样），回落离线照样能翻。

## 已知限制（实话实说）

- 悬浮窗在 Windows 下的效果、游戏全屏独占模式的表现，作者这边没有 Windows 环境，没法实测，以你实际用为准
- 游戏花体字、艺术字的 OCR 准确率没有实测数据，小字和特殊字体可能认不准
- 翻译质量是机器翻译水平，整句带上下文翻得比较准，单个词、缩写、专有名词可能翻错——翻错了就加一行纠错
- 离线引擎翻游戏黑话、碎片 UI 词不如在线引擎，离线是"不断线"的备胎，不是"翻得更好"的升级
- 离线翻 `FPS:186 PING:93MS` 这种带数字的行会翻不出来还多带"(英语)."，以及整段一起翻时个别短词可能被带偏（比如 `Drill` 单翻是"钻探"，跟别的行拼一段翻时曾出过"德里利语Name"）——固定短语的纠错写进 `user_corrections.txt` 最管用
- 首次运行要下载 OCR 模型，需要联网；首次用离线模式要下载翻译模型（约 70MB），需要联网

---

## In English (for international viewers)

**ROB RUN Real-Time Screen Translator (free, v3 offline-capable):** an overlay
for the Steam game ROB RUN — it OCRs English text on screen, translates it
to Chinese, and floats the translation over the original position, as if the
game shipped with Chinese. It only *looks* at the screen (screenshot → OCR →
machine translation → overlay); it never modifies game files, injects
anything, or reads game memory, so it does not trip Easy Anti-Cheat.
Online engine (free API) or offline engine (local Argos model); press F10
to switch. Includes a 1,590-entry Chinese–English glossary harvested from
real gameplay (`all-game-text-zh-en.md`).

Made so Chinese-speaking players can enjoy ROB RUN without staring at a
screen full of English they can't read. It's also for players who don't
want to pay for a game accelerator just for translation — accelerators
charge for that feature; this one is free.

One honest note: I don't have a Windows machine, so the overlay and
fullscreen-exclusive behavior are untested there — only the capture → OCR →
translate pipeline was verified on Linux. If you play on Windows, please
give it a try and open a GitHub Issue if something breaks (Windows version,
window mode, and a screenshot or the console error help a lot).

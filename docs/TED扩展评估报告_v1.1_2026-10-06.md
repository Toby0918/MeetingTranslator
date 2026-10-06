# MeetingTranslator 1.1.0：扩展 TED 评估

评估日期：2026-10-06。本次在 v1.0.0 基础上增加 10 场 TED，覆盖教育、行为、压力、运动、拒绝、对话、AI 安全、统计和脑科学。15 场合计 3 小时 5 分 33 秒，英语官方参考文本共 29,656 词。本次实际更改本地翻译模型，英文识别和分段保持 v1.0 实现。

## 结论与边界

最终 180 条固定英语输入的匿名 AI 对照中，忠实度由 2.7278 升到 2.8667，流畅度由 2.7000 升到 2.8722（0–4 分）。45 条忠实度提高、107 条持平、28 条下降。这是小幅改善，也有明确退步。两场未参与选型的独立演讲总体接近持平，不能据此证明稳定的泛化收益。AI 分数不是中文翻译准确率、人工审校或真实会议验收。

全部 1,171 条字幕用相同的 v1 英文识别结果重新运行最终生产翻译代码。最终有 1 条不可读译文，在本地解码重试后仍失败，保留英文并明确显示失败；该条恰好进入抽样，两个评分均为 0，没有被排除。v1 的全部固定字幕有 3 条明确失败，分别发生于 Urban、Robinson 和 Wernicke，最终的失败发生于 Wernicke。

本次 ASR 没有修改。15 场英语词错误总数为 2,364，WER 为 7.9714%，在版本对照中保持相同。素材比 v1 的五场更广，不能拿这个百分比与旧五场的 6.1680% 直接比较，也不能重复声称本轮降低了识别错误。

## 素材与划分

旧五场全部作为回归样本，旧版的 Duckworth 在本轮已不是未见验收样本。新增八场用于开发对照；Wernicke 和 Blakemore 两场在 checkpoint 选择前不读取译文或评分。它们的英语识别由同一未修改的 v1 流程完成，过程中仅查看汇总错误数，因此这里的独立性指翻译选型，而不是完全盲测的 ASR 研究。所有视频身份以 `scripts/ted_sources_v1.1.json` 中的 SHA-256 固定。

| 演讲 | 划分 | 时长 | 字幕数 | 英语 WER | 本地翻译失败 |
| --- | --- | ---: | ---: | ---: | ---: |
| [Matt Cutts：Try something new for 30 days](https://www.ted.com/talks/matt_cutts_try_something_new_for_30_days) | regression | 3:10 | 27 | 1.458% | 0 |
| [Julian Treasure：How to speak so that people want to listen](https://www.ted.com/talks/julian_treasure_how_to_speak_so_that_people_want_to_listen) | regression | 9:44 | 72 | 7.947% | 0 |
| [Hans Rosling：The best stats you've ever seen](https://www.ted.com/talks/hans_rosling_the_best_stats_you_ve_ever_seen) | regression | 19:33 | 106 | 7.821% | 0 |
| [Derek Sivers：How to start a movement](https://www.ted.com/talks/derek_sivers_how_to_start_a_movement) | regression | 2:53 | 14 | 3.404% | 0 |
| [Angela Lee Duckworth：Grit: The power of passion and perseverance](https://www.ted.com/talks/angela_lee_duckworth_grit_the_power_of_passion_and_perseverance) | regression | 5:59 | 52 | 0.812% | 0 |
| [Tim Urban：Inside the mind of a master procrastinator](https://www.ted.com/talks/tim_urban_inside_the_mind_of_a_master_procrastinator) | development | 13:54 | 95 | 9.257% | 0 |
| [Brené Brown：The power of vulnerability](https://www.ted.com/talks/brene_brown_the_power_of_vulnerability) | development | 20:03 | 104 | 5.786% | 0 |
| [Sir Ken Robinson：Do schools kill creativity?](https://www.ted.com/talks/ken_robinson_do_schools_kill_creativity) | development | 19:08 | 95 | 12.219% | 0 |
| [Kelly McGonigal：How to make stress your friend](https://www.ted.com/talks/kelly_mcgonigal_how_to_make_stress_your_friend) | development | 14:15 | 108 | 4.674% | 0 |
| [Wendy Suzuki：The brain-changing benefits of exercise](https://www.ted.com/talks/wendy_suzuki_the_brain_changing_benefits_of_exercise) | development | 12:53 | 81 | 4.688% | 0 |
| [Sebastian Wernicke：Lies, damned lies and statistics (about TEDTalks)](https://www.ted.com/talks/sebastian_wernicke_lies_damned_lies_and_statistics_about_tedtalks) | holdout | 5:42 | 28 | 23.197% | 1 |
| [Sarah-Jayne Blakemore：The mysterious workings of the adolescent brain](https://www.ted.com/talks/sarah_jayne_blakemore_the_mysterious_workings_of_the_adolescent_brain) | holdout | 14:09 | 73 | 7.464% | 0 |
| [Jia Jiang：What I learned from 100 days of rejection](https://www.ted.com/talks/jia_jiang_what_i_learned_from_100_days_of_rejection) | development | 15:22 | 119 | 12.576% | 0 |
| [Celeste Headlee：10 ways to have a better conversation](https://www.ted.com/talks/celeste_headlee_10_ways_to_have_a_better_conversation) | development | 11:20 | 65 | 8.513% | 0 |
| [Stuart Russell：3 principles for creating safer AI](https://www.ted.com/talks/stuart_russell_3_principles_for_creating_safer_ai) | development | 17:25 | 132 | 4.666% | 0 |

## 模型与实际训练

先比较提高解码搜索宽度、M2M100 和未微调的 Marian。较大的搜索宽度或换模型本身没有显示清晰收益。随后选择 [Helsinki-NLP/opus-mt-en-zh](https://huggingface.co/Helsinki-NLP/opus-mt-en-zh) 的固定版本，使用 AI 生成的 1,200 条原创、通用双语样例尝试小规模微调。生成提示不含 TED 全文、引文或参考译文；TED 只用于评估。样例覆盖日常会议、否定、不确定性、数字、单位、分句和习语，保存在 `training/synthetic-v1.1.json`，并未经过完整人工审校。

以 seed 20261006 确定划分，1,120 条训练、80 条合成验证。验证集与训练集规范化英语无完全重复，也没有超过 90% 字符相似的跨集合样例；开发 TED 参考文本中未发现至少八词的规范化英语完全匹配。这些检查不能证明语义独立。合成验证损失第一至第三轮为 1.0304、0.9889、0.9796，没有 epoch 0 对照，因此损失下降本身不能证明优于原模型。

checkpoint 选择对八场开发样本每场抽六条、五场回归样本每场抽四条，共 68 条。相同英语、相同有限前文下比较 v1、原始 Marian 和三轮微调模型，模型名称对 AI 评审隐藏。开发集合的忠实度／流畅度：

| 模型 | 忠实度 | 流畅度 |
| --- | ---: | ---: |
| v1 | 2.6250 | 2.7083 |
| 原始 Marian | 2.6667 | 2.5417 |
| epoch 1 | 3.1250 | 3.1667 |
| epoch 2 | 3.1458 | 3.1875 |
| epoch 3 | 3.0625 | 3.0833 |

按开发评分选择 epoch 2，并在读取首次 holdout 翻译评分前固定权重、beam 2 和不可读输出的 beam 4 重试。epoch 2 比 epoch 1 的差距仅每项一个总分，不能称为显著或稳定优势。最终选择的 CPU int8 `model.bin` SHA-256 为 `fe7fb315487364e8332525d9988b2d9d5398175b6a2e7d6f17a316c7e9271763`。训练配方在同一机器复跑，并重新转换得到相同权重散列；这不保证在不同硬件上逐字节相同。

生产程序指定 `>>cmn_Hans<<`，补源端 EOS，用不同的英语／中文 SentencePiece 分词器。保留既有按句处理、明确单词单位修正和不可读输出失败机制。模型训练使用 RTX 4080；发布运行程序使用 CPU，不需要 GPU、PyTorch 或 Transformers。来源、修改和 Apache 2.0 授权见第三方声明及 `licenses/`。

## 冻结后的最终对照

权重冻结后，完整便携包的原创固定自检句 `Write 500 words.` 暴露出“五百个字”未被旧计数守卫修正的问题。新增失败测试后，仅把明确数值后面的“字”规则扩展为允许“个字”，并保留字符／字节及等值混合单位排除。这一修复由通用自检句触发，未根据 TED 译文选新模型或调整训练、beam 参数。全部 1,171 条重新翻译，4 条译文改变，分别是 Cutts 索引 13、Headlee 索引 55／56、Wernicke 索引 5。

这一步发生在首次 holdout 结果已读之后，故最终版本不应称为“所有处理完全冻结的一次盲测”。两篇演讲未用于训练或权重选型；通用后处理修复也作用于其中一条。新一轮在独立目录重新评分，没有复用旧结果。首次 180 对评分为忠实度 2.7667→2.8778、流畅度 2.7278→2.9111、43／107／30，最终结果见下表。多数输入没有变化而评分发生波动，不能把两轮评分差异全部归因于这四条修复；两个结果均保存在机器可读摘要中。

最终评估每场取 12 个均匀分布的字幕索引，共 180 对。每篇 A/B 位置均衡为 6/6，seed 固定；非随机抽样适合诊断，不能代表全部字幕的无偏准确率。两份译文共用同一 v1 英文与前两段有限上下文。评审只按当前英文评分，不知道候选模型名，不用中文官方字幕补齐缺失原文，未说完的原文按未完成句处理。评分输入、模型权重、代码及评审参数绑定 SHA-256；不同输入不得复用旧评分。

| 集合 | 对照数 | v1 忠实度 | v1.1 忠实度 | v1 流畅度 | v1.1 流畅度 | 改善／持平／下降 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 全部 | 180 | 2.7278 | 2.8667 | 2.7000 | 2.8722 | 45／107／28 |
| development | 96 | 2.8021 | 2.9688 | 2.7604 | 2.9583 | 23／59／14 |
| regression | 60 | 2.6000 | 2.7500 | 2.5833 | 2.8000 | 16／36／8 |
| holdout | 24 | 2.7500 | 2.7500 | 2.7500 | 2.7083 | 6／12／6 |

初筛的五候选评分与最终双候选评分是不同评审任务、不同样本集合，分数不可混成一组实验。DeepSeek 同时生成合成训练数据和提供自动评分，可能偏好自身的表达方式。评审未做重复随机抽样、跨供应商验证、置信区间或人工复核。holdout 仅 24 对、两个演讲，最终忠实度持平（2.75→2.75）、流畅度略降（2.75→2.7083），不能说明对全部会议或新领域稳定改善。数字、否定和单位仍会被模型误译；可读文本检查只能发现部分字符问题，不能保证语义正确。

新增十场的固定 v1 英文也完成全文 AI 参考翻译，900 次请求中 899 次成功、1 次失败。该批参考生成于候选冻结后，不用于模型训练或 checkpoint 选择；失败明确记录，无静默重试。旧五场的上一轮 266 次 AI 翻译仍保留为历史对照，两轮英语片段不完全相同，不能把这两个计数当作本轮 1,171 条的一一对应参考全集。

最终本地翻译总耗时 47.40 秒，单段平均 0.0405 秒、95 分位 0.0704 秒。本次是文件译文刷新，未包括等待停顿、分段和 ASR，不代表实时字幕延迟。不同版本计时条件不同，不能声称本次已证明速度提升。

## 可复现证据与运行验证

`benchmark-summary.json` 仅保存汇总和逐篇统计，不含完整字幕；`mt-pair-scores-v1.1.json` 保存 180 个索引、输入散列和评分，可独立重算均分及胜负计数。官方 TED 原始视频、英文／中文 VTT、完整识别和译文只保存在本机忽略缓存，不进入仓库或发布包。原创合成训练样例可以随包核查。

完整音频可用 `python scripts/evaluate_ted.py --download --models MODEL_ROOT --save-captions --caption-name v1.json --output .bench/asr-summary.json` 重跑。v1.0 对照应指定 v1.0 Release 中的原始 Argos 模型目录，不加 `--baseline`；该参数专指最早的 pre-v1 单句／分段策略。固定英文对照可用 `python scripts/benchmark_ted_translation.py --models V1_1_MODEL_ROOT --baseline-name v1.json` 重跑本地译文；明确加 `--ai-review` 才会发送文本到 DeepSeek 评分，需要自己的密钥和余额。缓存及全文输出应留在 `.bench/`。

训练复现见 `training/README.md`、`scripts/train_offline_mt.py` 和 `mt-training-v1.1.json`。AI 服务的后续响应可能改变，不保证评分逐次相同。本轮 60 项自动测试通过，覆盖新模型的源／目标分词器、语言标记、重试、中文路径和模型缺失，原有设备、停止、分段、凭据及云端错误测试继续通过。生产改动及方法经过独立只读复查。

Windows 便携包另行执行完整解压与文件校验、含中文和空格的路径启动、移除开发 Python 和密钥环境、离线设置与关闭代理端口、真实隐藏界面创建、设备枚举、本地模型加载及真实 TED 短音频识别翻译。发布验证记录在仓库的 `release-verification.json`，完成包验证后填写；不代表第二台电脑或新真实 Zoom／Teams／多人麦克风验收。程序仍未进行商业代码签名。

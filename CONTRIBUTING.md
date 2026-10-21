# 贡献指南

欢迎补充 2026 年及以后的 GDC 资料、修正中英文摘要或提交工具改进。

1. 找到 `data/<年份>/sessions.json` 中对应的演讲 ID；新资料尽量先用官方目录采集器收录。
2. 修改参考译名、双语摘要或链接。提供来源；没有可核实的简介时保留“待整理”。
3. YouTube 需为实际演讲播放链接，并填写频道、核验日期与 `evidence_url`。搜索页或播放列表请勿作为单场视频提交。
4. 执行以下检查，再提交数据和生成后的 Markdown。

```bash
python -m gdc_index validate
python -m gdc_index build
python -m unittest discover -s tests -v
python -m gdc_index build --check
```

AI 辅助翻译和归纳请标为 `draft`；核对官方简介、术语、讲者和英文含义后才改成 `reviewed`。不要根据标题臆造演讲结论。未观看完整演讲时只整理简介导读。请勿上传完整视频、付费内容、完整官方简介、缓存、API 密钥或个人信息。

文章与视频的填写方式、离线队列和年度更新流程见 [维护指南](docs/MAINTAINING.md)。

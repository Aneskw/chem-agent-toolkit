# P1 v2：破坏性 chunk framing 与 TLS 异常关闭（结论仅限本版本这些构造）

CLI `codex-cli 0.164.0-alpha.11.1`，SHA-256 `1103e9e0…58a098`。回环端点、合成输入、独立临时 `CODEX_HOME`、无凭据、**零模型调用**。
结果：`validation/planner-attribution/p1v2-20261027T015417Z/`（`results.json`、`summary.json`、`raw/<scenario>.bin` 保存实际写出的原始字节）。
每轮都保留控制场景；每行记录 CLI 版本、`config.toml` 的 SHA-256、原始响应字节数、stdout 事件序列、命中的 stderr 类别、退出码。

## 结果

| 场景 | 传输 | framing 独立判定（直接解析 chunk + h11 复核） | CLI 行为 | 退出码 |
| --- | --- | --- | --- | --- |
| `control_complete` | http | 有效：chunked 终止符存在；h11 `MUST_CLOSE` | 正常完成 | 0 |
| `bad_chunk_framing` | http | **无效**：`chunk declares 4096 bytes but only 711 remain`；h11 `SEND_BODY` | **仍成功**，无错误类别 | 0 |
| `tls_close_before_completed` | https | 字节流本身完整（终止符存在），但连接在 completed 前关闭；h11 `protocol error: Got data when expecting EOF` | `stream closed before response.completed` | 1 |
| `tls_close_after_completed` | https | 完整，completed 后关闭 | 成功 | 0 |

## 本版本这些构造中的行为（可直接引用）

1. **`bad_chunk_framing` 这次确实非法**：直接解析显示首个 chunk 声明 4096 字节而实际只剩 711 字节，h11 独立复核为 `SEND_BODY`。上一次“成功”的行因此被替换——不是因为容忍非法 framing，而是因为**事件序列在该 chunk 内已完整送达**，CLI 在收到完整事件序列后不因后续 framing 断裂而失败。
2. **TLS 异常关闭的表现取决于位置**：completed 之前关闭 → `stream closed before response.completed`（退出码 1）；completed 之后关闭 → 成功（退出码 0）。与 v1 的 HTTP 观察一致。
3. **私有 CA 可对子进程生效且不牺牲校验**：通过子进程环境 `SSL_CERT_FILE`/`NODE_EXTRA_CA_CERTS` 指向本地自签证书（`summary.json` 中 `tls_private_ca_usable: true`），**未关闭证书校验、未写系统信任库、未做 MITM**。若该方式不可用，脚本会记录 “TLS cases could not be exercised” 而不是降级校验。

## 明确不作结论

- 不宣称错误文本互斥：本矩阵只覆盖四种构造，`Failed to parse SSE event` 等文本在更复杂形态下的来源未穷举。
- 不据此定位线上根因：batch-3 的错误与“completed 前关闭”相容，但合成构造不能证明线上只能由该原因产生；服务端、中间层、代理、CLI 解码仍不可区分。
- 各次运行的 `raw/*.bin` 只证明“我们写出这些字节”，不证明对端如何读取。

## 复现

```powershell
python validation/planner-attribution/p1_stream_matrix_v2.py
```

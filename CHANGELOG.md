# Changelog

All notable changes to this project will be documented in this file.

## [0.0.1.0] - 2026-04-05

### Fixed
- 公積金輸入：「取消」指令現在在格式驗證前先被攔截，避免使用者輸入「取消」卻收到格式錯誤訊息
- 公積金輸入：新增金額必須大於 0 的驗證，防止輸入 0 或負數
- 結清流程：當 settle 指令格式不正確時，回覆明確的錯誤提示而非靜默失敗
- 試算表標頭解析：去除欄位名稱中的 `\n(...)` 說明後綴，與 `update_event_status` 保持一致，修正 `mark_family_settled` 無法找到正確欄位的問題
- 全形數字輸入：將 `isdigit()` 改為 ASCII 數字正則比對，防止全形數字（如 `１２３`）導致 `int()` 崩潰

# ComfyUI-Notifier 功能更新

## 更新内容（2026-03-18）

### 1. Audio 音频格式和质量支持

#### 之前状态
- Audio格式：固定为 **flac**
- Audio质量：固定为 **128k**
- 无法自定义

#### 现在支持
新增两个可选参数：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `audio_format` | String | "auto" | 音频格式选择: `auto`, `flac`, `mp3`, `wav`, `opus` |
| `audio_quality` | String | "auto" | 音频质量/比特率: `auto`, `128k`, `192k`, `256k`, `320k` |

**示例**：
```
audio_format = "mp3"
audio_quality = "256k"
```

**向后兼容性**：
- 默认值为 "auto"，自动使用原有的 flac + 128k 配置
- 现有的工作流不需要任何改动

---

### 2. Video 视频格式支持

#### 之前状态
- Video 仅支持 STRING 类型（文件路径）
- 无法处理原生 ComfyUI VIDEO 数据类型
- 无法自定义视频格式/编码

#### 现在支持
新增参数：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `video_format` | String | "auto" | 视频编码格式选择: `auto`, `h264`, `h265`, `vp9` |

**向后兼容性**：
- 默认值为 "auto"
- 现有的 video STRING 路径输入方式保持不变
- 今后可扩展支持原生 VIDEO 类型输入

---

### 3. 支持的媒体格式

#### Audio 支持格式
```
✓ FLAC (.flac)  - 默认
✓ MP3  (.mp3)
✓ WAV  (.wav)
✓ Opus (.opus)
✗ OGG, M4A, AAC - 内部格式转换
```

#### Video 支持格式
```
✓ MP4    (.mp4)   - h264/h265
✓ MOV    (.mov)
✓ MKV    (.mkv)
✓ WebM   (.webm)  - vp9
✓ AVI    (.avi)
✓ M4V    (.m4v)
✓ MPEG   (.mpeg, .mpg)
```

---

### 4. 实现细节

#### 修改的文件

**nodes.py**
- 新增 input_types 中的可选参数（不影响现有必需参数）
- try_notify 方法签名扩展，新参数传递到 notify_all

**media_adapter.py**
- `resolve_payload()` - 新增参数支持
- `_payload_from_audio()` - audio_format/audio_quality 参数化
- `_hash_audio()` - 缓存键包含新参数，避免冲突
- `_resolve_audio_format()` - 新方法，处理格式解析逻辑
- `_payload_from_path()` - 预留 video_format 参数

**notify.py**
- notify_all 通过 **media_inputs 自动传递新参数
- 无需修改，向前兼容

---

### 5. 使用示例

#### 基础使用（保持原有方式）
```python
# 使用默认设置：flac + 128k
image = ...  # IMAGE 数据
audio = ...  # AUDIO 数据
```

#### 自定义 Audio 格式和质量
```python
audio_format = "mp3"      # 改用 MP3 格式
audio_quality = "256k"    # 设定质量为 256kbps
```

#### 组合使用
```python
image = ...
audio = ...
audio_format = "wav"      # 不压缩，使用 WAV
audio_quality = "320k"    # 最高质量（对 mp3 有效）
video_format = "h265"     # 现代视频编码（预留）
```

---

### 6. 缓存机制

- 音频缓存键现已包含格式和质量参数
- 相同音频内容，不同格式/质量会被视为不同的输出文件
- 避免了格式修改后仍然使用旧缓存的问题

---

### 7. 兼容性说明

✅ **完全向后兼容**
- 所有新参数均为可选，拥有合理默认值
- 现有工作流无需任何修改
- 现有调用方式继续正常工作

---

### 8. 未来扩展方向

- [ ] 支持原生 ComfyUI VIDEO 类型输入
- [ ] 更多 audio_quality 预设（如 "64k", "flac" 无损）
- [ ] 更多 video_format 选项（如 av1 等）
- [ ] 视频分辨率/帧率 参数控制
- [ ] 音频采样率选项


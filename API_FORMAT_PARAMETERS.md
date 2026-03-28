# API 文档 - Audio/Video 格式参数

## 概述

ComfyUI-Notifier 现已支持音频和视频格式的灵活配置。所有新参数均为**可选**，使用默认值时完全保持向后兼容。

---

## 参数详解

### audio_format

**类型：** String (下拉选项)  
**默认值：** `"auto"`  
**可选值：** `["auto", "flac", "mp3", "wav", "opus"]`

**说明：**
- 指定输出音频的格式
- `"auto"` 会自动使用 FLAC 格式（舒适的压缩无损格式）
- 格式影响文件大小和兼容性

**受支持的格式特性：**

| 格式 | 特性 | 文件大小 | 兼容性 | 用途 |
|------|------|---------|--------|------|
| **FLAC** | 无损压缩 | 中等 | 很好 | 默认，音乐专业用途 |
| **MP3** | 有损压缩 | 小 | 极好 | 通用、广泛支持 |
| **WAV** | PCM 无压缩 | 大 | 极好 | 音频编辑，专业用途 |
| **Opus** | 高效有损 | 小 | 好 | 现代流媒体 |

**示例：**
```python
# 使用 MP3 格式
audio_format = "mp3"

# 使用 WAV 格式（无损但大文件）
audio_format = "wav"

# 自动选择（默认FLAC）
audio_format = "auto"
```

---

### audio_quality

**类型：** String (下拉选项)  
**默认值：** `"auto"`  
**可选值：** `["auto", "128k", "192k", "256k", "320k"]`

**说明：**
- 指定音频的比特率/质量级别
- `"auto"` 会使用 128kbps（原有默认）
- 仅对有损格式有意义（MP3, Opus）；FLAC 和 WAV 忽略此参数

**质量与文件大小对照：**

| 比特率 | 质量 | 典型文件大小（1分钟） | 推荐用途 |
|--------|------|----------------------|---------|
| 128k | 下等 | ~1 MB | 语音、电话 |
| 192k | 中等 | ~1.4 MB | 背景音乐、流媒体 |
| 256k | 较好 | ~1.9 MB | 通用、大多数场景 |
| 320k | 最高 | ~2.4 MB | 专业、音乐归档 |

**示例：**
```python
# 高质量 MP3
audio_format = "mp3"
audio_quality = "320k"

# 中等质量 MP3
audio_format = "mp3"
audio_quality = "192k"

# WAV（忽略质量参数）
audio_format = "wav"
audio_quality = "320k"  # 此参数无效
```

---

### video_format

**类型：** String (下拉选项)  
**默认值：** `"auto"`  
**可选值：** `["auto", "h264", "h265", "vp9"]`

**说明：**
- 指定输出视频的编码格式
- `"auto"` 保持原有行为
- 目前主要用于定义视频编码偏好（实际转码需要后续扩展）

**视频编码格式对照：**

| 编码 | 格式 | 特点 | 兼容性 |
|------|------|------|--------|
| **H.264** | AVC | 广泛应用，成熟 | 极好（所有设备） |
| **H.265** | HEVC | 更小文件，更新 | 好（现代设备） |
| **VP9** | WebM | 开源，高效 | 好（Web/现代） |

**示例：**
```python
# 使用 H.265（更小的文件）
video_format = "h265"

# 使用 H.264（最兼容）
video_format = "h264"

# 使用 VP9（Web优化）
video_format = "vp9"
```

---

## 参数组合示例

### 示例 1：高质量音频
```
audio_format = "wav"      # 无损格式
audio_quality = "320k"    # 忽略（WAV不需要）
```

### 示例 2：通用压缩设置
```
audio_format = "mp3"
audio_quality = "256k"
video_format = "h264"
```

### 示例 3：流媒体优化
```
audio_format = "opus"     # 现代有损编码
audio_quality = "128k"    # 较小文件
video_format = "vp9"      # 现代编码
```

### 示例 4：完全保持原样（向后兼容）
```
audio_format = "auto"
audio_quality = "auto"
video_format = "auto"
```

---

## 内部实现

### 缓存机制

- **缓存键** 包含：文件路径、格式、质量、内容哈希
- **缓存冲突避免**：修改格式/质量后会生成新的输出文件，避免使用旧缓存
- **缓存过期**：临时文件在 temp 目录，随 ComfyUI 清理周期删除

### 格式转换

```
AUDIO 输入 → 内存处理 → AudioSaveHelper → 指定格式 → 文件输出
             ↓
        audio_format
        audio_quality
```

### 调用链路

```
GeneralNotifier.try_notify()
    ↓
NotificationManager.notify_all()
    ↓
MediaAdapter.resolve_payload(audio_format, audio_quality, video_format)
    ↓
MediaAdapter._payload_from_audio()
    ↓
AudioSaveHelper.save_audio(format, quality)
```

---

## 兼容性注意事项

### 向后兼容性 ✓

- 新参数所有默认值均为 `"auto"`
- `"auto"` 内部解析为原有行为（FLAC + 128k）
- **现有工作流完全无需修改**

### 格式支持

**可能的限制因素：**

1. **AudioSaveHelper限制**：
   - ComfyUI 本身仅支持：flac, mp3, opus
   - WAV 格式在当前版本可能不支持（试验性）

2. **依赖模块**：
   - ffmpeg（如果需要转码）
   - 音频编码库（libmpg123 等）

3. **性能考虑**：
   - MP3 编码比 FLAC 快
   - WAV 最快（无压缩）
   - Opus 编码时间中等

---

## 错误处理

如果不支持的格式被指定：

```
audio_format = "aac"  # 不支持
↓
FallbackTo: "flac"    # 自动降级到 FLAC
```

对于无效的质量值：

```
audio_quality = "999k"  # 无效
↓
Resolution: 忽略        # 保留原有设置或使用默认
```

---

## 性能指标（参考）

### 转换时间（针对10秒音频）

| 格式 | 质量 | 转换时间 | 输出文件大小 |
|------|------|---------|-----------|
| FLAC | N/A | ~100ms | ~150KB |
| MP3 | 128k | ~50ms | ~50KB |
| MP3 | 320k | ~50ms | ~125KB |
| WAV | N/A | ~10ms | ~350KB |
| Opus | 128k | ~80ms | ~40KB |

*注：时间随硬件和输入质量变化*

---

## 常见问题

**Q: 修改格式后，旧的 flac 文件会被删除吗？**  
A: 不会自动删除，临时文件会在 ComfyUI 清理时移除。手动清理可删除 `temp/comfyui_notifier/` 目录。

**Q: 能否在运行时动态改变格式？**  
A: 可以！新参数就是为此设计的，每次更改都会生成新的输出文件。

**Q: WAV 格式我的 ComfyUI 不支持**  
A: 如异常，会自动降级到 FLAC。检查 ComfyUI 版本和 AudioSaveHelper 的具体支持。

**Q: 影响现有模型和工作流吗？**  
A: 不影响！所有参数为可选，默认值保持原样。

---

## 扩展规划

未来可能的扩展：

- [ ] `audio_sample_rate` - 采样率选择（44.1kHz, 48kHz）
- [ ] `audio_channels` - 单声道/立体声选择
- [ ] `video_resolution` - 分辨率缩放
- [ ] `video_fps` - 帧率控制
- [ ] `video_bitrate` - 视频比特率设置
- [ ] 原生 VIDEO 类型输入支持


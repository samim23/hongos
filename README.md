# HONGOS - Open Source Tool for Autonomous Video Production - One Prompt Generates Script, Images, Voices, Videos & Final Edit

![HONGOS UI Screenshot](https://samim.io/static/upload/Screenshot-20250318163704-1337x908.png)

HONGOS is an AI video production tool that generates complete video stories with coherent narrative flow and visual style end-to-end from a single text prompt in just minutes. Useful for advertising, social media, comedy, and more.

1. **Script & Image Generation**: Creates both a compelling narrative script and a sequence of story frames using Google's Gemini 2.0 Flash model
2. **Text-to-Speech Narration**: Adds professional voice narration for each scene using ElevenLabs
3. **Image-to-Video Animation**: Transforms static images into fluid animations using Google's veo2 or Luma's ray2 model
4. **Background Music**: Adds YouTube music tracks to complete the experience
5. **Final Editing**: Automatically combines all elements into a cohesive final video

## ✨ Features

- One-click video creation from a single text prompt
- Use your own image as a starting point to drive the story & video style
- Flexible usage via web interface or command line for automation

## 🎬 Examples

[View Demo Video](https://youtu.be/your-demo-video)

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- [yt-dlp](https://github.com/yt-dlp/yt-dlp#installation) for YouTube audio download
- API keys for:
  - [Google Gemini](https://ai.google.dev/)
  - [ElevenLabs](https://elevenlabs.io/)
  - [FAL](https://fal.ai/)

### Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/samim23/hongos.git
   cd hongos
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Set up your API keys in one of two ways:

   a. Create a `.env` file with your API keys (see `.env.example`):

   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

   b. Or simply enter your API keys directly in the web UI when prompted

4. Run the application:

   ```bash
   python main.py
   ```

5. Open your browser and go to:
   ```
   http://localhost:8000
   ```

![HONGOS Banner](https://samim.io/static/upload/Generated_Image_March_18_2025_-_4_28PM.png.jpeg)

A [samim.io](https://samim.io) production. Dropping AI Computational Comedy heat since 2010 🔥

# HONGOS - AI Story Video Generator

![HONGOS Banner](https://i.imgur.com/placeholder.png)

HONGOS is an AI-powered story video generator that creates animated sequences from text prompts. It combines multiple AI technologies to generate a complete storytelling experience:

1. **Text-to-Image Generation**: Creates a sequence of story frames using Google's Gemini model
2. **Text-to-Speech Narration**: Adds voice narration for each scene using ElevenLabs
3. **Image-to-Video Animation**: Transforms static images into fluid animations using FAL's veo2 model
4. **Background Music**: Adds YouTube music tracks to complete the experience

## 🎬 Examples

[View Demo Video](https://youtu.be/your-demo-video)

![Example Animation](https://i.imgur.com/placeholder.gif)

## ✨ Features

- Generate multi-frame story sequences from text prompts
- Create animated videos from static images
- Add professional voice narration to each scene
- Include background music from YouTube
- Use your own image as a starting point
- Simple web interface for easy use

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
   git clone https://github.com/yourusername/hongos.git
   cd hongos
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file with your API keys (see `.env.example`):

   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

4. Run the application:

   ```bash
   python main.py
   ```

5. Open your browser and go to:
   ```
   http://localhost:8000
   ```

## 🔧 Configuration

### Environment Variables

Create a `.env` file in the project root with the following variables:

GEMINI_API_KEY=your_gemini_api_key
ELEVENLABS_API_KEY=your_elevenlabs_api_key
FAL_KEY=your_fal_api_key

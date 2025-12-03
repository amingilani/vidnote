import unittest
from unittest.mock import MagicMock, patch, mock_open
import sys
import os

# Add current directory to sys.path so we can import main
sys.path.append(os.getcwd())
import main

class TestVideoProcessor(unittest.TestCase):

    @patch('os.system')
    def test_extract_audio_success(self, mock_system):
        mock_system.return_value = 0
        main.extract_audio("input.mp4", "output.mp3")
        mock_system.assert_called_once()
        self.assertIn("ffmpeg", mock_system.call_args[0][0])

    @patch('os.system')
    def test_extract_audio_failure(self, mock_system):
        mock_system.return_value = 1
        with self.assertRaises(RuntimeError):
            main.extract_audio("input.mp4", "output.mp3")

    @patch('whisper.load_model')
    def test_transcribe_audio(self, mock_load_model):
        mock_model = MagicMock()
        mock_load_model.return_value = mock_model
        mock_model.transcribe.return_value = {"text": "hello"}
        
        result = main.transcribe_audio("audio.mp3")
        
        mock_load_model.assert_called_with("base")
        mock_model.transcribe.assert_called_with("audio.mp3")
        self.assertEqual(result, {"text": "hello"})

    @patch('main.VideoManager')
    @patch('main.SceneManager')
    @patch('cv2.VideoCapture')
    @patch('cv2.imwrite')
    def test_extract_slides(self, mock_imwrite, mock_videocapture, mock_scenemanager, mock_videomanager):
        # Setup mocks
        mock_vm_instance = mock_videomanager.return_value
        mock_sm_instance = mock_scenemanager.return_value
        mock_cap_instance = mock_videocapture.return_value
        
        # Mock scene list: [(start_time, end_time), ...]
        # Timecode objects in scenedetect usually have get_seconds()
        mock_t1 = MagicMock()
        mock_t1.get_seconds.return_value = 10.0
        mock_t2 = MagicMock()
        mock_t2.get_seconds.return_value = 20.0
        
        # Scene is a tuple of (start, end, ...)
        mock_sm_instance.get_scene_list.return_value = [(mock_t1, mock_t2)]
        
        # Mock VideoCapture read
        mock_cap_instance.read.return_value = (True, "fake_frame_data")
        
        slides = main.extract_slides("video.mp4", "output_dir")
        
        self.assertEqual(len(slides), 1)
        self.assertEqual(slides[0]['timestamp'], 10.0)
        self.assertEqual(slides[0]['image_filename'], "scene_001.jpg")
        
        mock_videomanager.assert_called_with(["video.mp4"])
        mock_sm_instance.detect_scenes.assert_called()
        mock_cap_instance.set.assert_called()
        mock_imwrite.assert_called()

    def test_generate_markdown(self):
        transcript = {
            "segments": [
                {"start": 0.0, "text": "Intro text."},
                {"start": 15.0, "text": "Slide 1 text."}
            ]
        }
        slides = [
            {"timestamp": 10.0, "image_filename": "slide1.jpg", "end_timestamp": 20.0}
        ]
        
        with patch("builtins.open", mock_open()) as mock_file:
            main.generate_markdown(transcript, slides, "output.md")
            
            handle = mock_file()
            # Check if writes happened
            self.assertTrue(handle.write.called)
            
            # We can inspect what was written if we want to be specific
            # But just checking it runs without error and writes something is a good start
            written_content = "".join(call.args[0] for call in handle.write.call_args_list)
            self.assertIn("# Video Transcript", written_content)
            self.assertIn("Intro text.", written_content)
            self.assertIn("![Scene 1](images/slide1.jpg)", written_content)

if __name__ == '__main__':
    unittest.main()

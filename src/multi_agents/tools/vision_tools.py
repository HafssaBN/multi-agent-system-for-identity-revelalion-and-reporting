from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from ..constants.constants import Constants
import logging
import requests
from io import BytesIO
from PIL import Image

class VisionTools:
    def __init__(self):
        self.llm = ChatOpenAI(
            base_url=Constants.OPENROUTER_BASE_URL,
            api_key=Constants.OPENROUTER_API_KEY,
            model_name=Constants.DEFAULT_MODEL,
            temperature=0.1
        )
        self.logger = logging.getLogger(__name__)
    
    def compare_profile_pictures(self, image_urls: Dict[str, str]) -> Dict[str, Any]:
        """
        Compare two profile pictures and assess their similarity.
        
        Args:
            image_urls: Dictionary with 'image1' and 'image2' URLs
            
        Returns:
            Dictionary with 'confidence' (Low/Medium/High) and 'justification'
        """
        try:
            # Download images
            response1 = requests.get(image_urls["image1"])
            response2 = requests.get(image_urls["image2"])
            
            img1 = Image.open(BytesIO(response1.content))
            img2 = Image.open(BytesIO(response2.content))
            
            # Convert to base64 for the LLM
            buffered1 = BytesIO()
            buffered2 = BytesIO()
            img1.save(buffered1, format="PNG")
            img2.save(buffered2, format="PNG")
            
            img1_str = buffered1.getvalue()
            img2_str = buffered2.getvalue()
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", """Analyze these two profile pictures and determine if they likely show the same person.
                 
                 Consider:
                 - Facial features
                 - Hairstyle
                 - Background/setting
                 - Any distinctive elements
                 
                 Return JSON with 'confidence' (Low/Medium/High) and 'justification'."""),
                ("human", [
                    {"type": "text", "text": "Image 1:"},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img1_str}"}},
                    {"type": "text", "text": "Image 2:"},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img2_str}"}}
                ])
            ])
            
            chain = prompt | self.llm
            result = chain.invoke({})
            
            return {
                "confidence": result.get("confidence", "Low"),
                "justification": result.get("justification", ""),
                "success": True
            }
        except Exception as e:
            self.logger.error(f"Image comparison failed: {str(e)}")
            return {
                "confidence": "Low",
                "justification": f"Error during comparison: {str(e)}",
                "success": False
            }

# Initialize tool
compare_profile_pictures = VisionTools().compare_profile_pictures
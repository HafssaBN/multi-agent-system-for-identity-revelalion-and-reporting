# src/multi_agents/tools/vision_tools.py
from langchain_core.tools import tool
from typing import Dict, Any, List, Union
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from ..constants.constants import Constants
import logging
import requests
from io import BytesIO
from PIL import Image
import base64
import json
from pydantic import SecretStr

class VisionTools:
    def __init__(self):
        self.llm = ChatOpenAI(
            base_url=Constants.OPENROUTER_BASE_URL,
            api_key=SecretStr(Constants.OPENROUTER_API_KEY or ""),
            # --- This now correctly points to the verified model in constants.py ---
            model=Constants.VISION_MODEL,
            temperature=0.1,
            max_completion_tokens = 4096
        )
        self.logger = logging.getLogger(__name__)
    
    def compare_profile_pictures(self, image_sources: Union[Dict[str, str], List[str]]) -> Dict[str, Any]:
        """
        Compares two profile pictures from URLs using a powerful open-source Vision LLM (LLaVA)
        and assesses if they show the same person.
        """
        try:
            # Robust input parsing
            urls_to_compare = []
            if isinstance(image_sources, dict):
                urls_to_compare = list(image_sources.values())
            elif isinstance(image_sources, list):
                urls_to_compare = image_sources

            if len(urls_to_compare) < 2:
                return {"success": False, "justification": "Error: At least two image URLs are required."}
            
            url1, url2 = urls_to_compare[0], urls_to_compare[1]
            self.logger.info(f"Comparing image 1: {url1}")
            self.logger.info(f"Comparing image 2: {url2}")

            # Image Downloading & Processing
            response1 = requests.get(url1, timeout=15)
            response2 = requests.get(url2, timeout=15)
            response1.raise_for_status()
            response2.raise_for_status()
            
            img1 = Image.open(BytesIO(response1.content))
            img2 = Image.open(BytesIO(response2.content))
            
            buffered1, buffered2 = BytesIO(), BytesIO()
            img1.convert("RGB").save(buffered1, format="PNG")
            img2.convert("RGB").save(buffered2, format="PNG")
            
            img1_str = base64.b64encode(buffered1.getvalue()).decode('utf-8')
            img2_str = base64.b64encode(buffered2.getvalue()).decode('utf-8')
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are a world-class forensic analyst. Your sole mission is to compare two images and determine if they show the same person. Your response MUST be a single, valid JSON object with two keys: "confidence" (a string: "Low", "Medium", or "High") and "justification" (a string explaining your reasoning)."""),
                ("human", [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img1_str}"}},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img2_str}"}}
                ])
            ])
            
            chain = prompt | self.llm
            result = chain.invoke({})
            
            # Robust output parsing
            self.logger.info(f"VLLM returned content: {result.content}")
            content_str = str(result.content).strip().replace("```json", "").replace("```", "")
            parsed_result = json.loads(content_str)
            
            return {
                "confidence": parsed_result.get("confidence", "Low"),
                "justification": parsed_result.get("justification", "Could not parse justification."),
                "success": True
            }
        except Exception as e:
            self.logger.error(f"Image comparison failed with a critical error: {str(e)}")
            return {
                "confidence": "Low",
                "justification": f"Error during comparison: {str(e)}",
                "success": False
            }

compare_profile_pictures = VisionTools().compare_profile_pictures

# NEW: LangChain tool wrapper so it can be bound in get_all_tools()
@tool("compare_profile_pictures_tool")
def compare_profile_pictures_tool(image_sources: Union[Dict[str, str], List[str]]) -> Dict[str, Any]:
    """
    Takes either a dict of URLs or a list of image URLs (must be >= 2).
    Returns {"confidence": "Low|Medium|High", "justification": "...", "success": bool}
    """
    vt = VisionTools()
    return vt.compare_profile_pictures(image_sources)
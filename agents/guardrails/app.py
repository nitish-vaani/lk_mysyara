from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import yaml
import re
import logging
import os
from typing import Dict, Any, List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Custom Guardrails Validation API",
    description="A FastAPI application for input validation using custom YAML-based guardrails",
    version="1.0.0"
)

class InputRequest(BaseModel):
    text: str

class ValidationResponse(BaseModel):
    is_safe: bool
    response: str = ""
    metadata: Dict[str, Any] = {}
    error: str = ""

class GuardrailsEngine:
    """Custom guardrails engine that processes your YAML configuration format"""
    
    def __init__(self, config_path: str = "./rails"):
        self.config_path = config_path
        self.validators = {}
        self.flows = {}
        self.rails_config = {}
        self.load_configuration()
    
    def load_configuration(self):
        """Load all YAML configuration files"""
        try:
            # Load guardrails.yaml
            guardrails_file = os.path.join(self.config_path, "guardrails.yaml")
            if os.path.exists(guardrails_file):
                with open(guardrails_file, 'r') as f:
                    guardrails_config = yaml.safe_load(f)
                    if 'validators' in guardrails_config:
                        for validator in guardrails_config['validators']:
                            self.validators[validator['name']] = validator
                    logger.info(f"Loaded {len(self.validators)} validators from guardrails.yaml")
            
            # Load flows.yaml
            flows_file = os.path.join(self.config_path, "flows.yaml")
            if os.path.exists(flows_file):
                with open(flows_file, 'r') as f:
                    flows_config = yaml.safe_load(f)
                    if 'flows' in flows_config:
                        for flow in flows_config['flows']:
                            self.flows[flow['name']] = flow
                    logger.info(f"Loaded {len(self.flows)} flows from flows.yaml")
            
            # Load prompt.yaml (rails configuration)
            prompt_file = os.path.join(self.config_path, "prompt.yaml")
            if os.path.exists(prompt_file):
                with open(prompt_file, 'r') as f:
                    self.rails_config = yaml.safe_load(f)
                    logger.info("Loaded rails configuration from prompt.yaml")
                    
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            raise
    
    def validate_input(self, text: str) -> Dict[str, Any]:
        """Validate input text using the loaded configuration"""
        try:
            # Get input rails from prompt.yaml
            input_rails = self.rails_config.get('rails', {}).get('input', [])
            
            # Run each validator specified in input rails
            violations = []
            blocked_by = []
            
            for validator_name in input_rails:
                if validator_name in self.validators:
                    validator = self.validators[validator_name]
                    is_valid, violation_msg = self._run_validator(validator, text)
                    
                    if not is_valid:
                        violations.append(violation_msg)
                        blocked_by.append(validator_name)
            
            # Check if input failed any validators
            is_safe = len(violations) == 0
            
            # If not safe, check for flows that handle the failure
            response_message = ""
            if not is_safe:
                response_message = self._get_failure_response(blocked_by[0] if blocked_by else None)
            
            return {
                "is_safe": is_safe,
                "response": response_message,
                "violations": violations,
                "blocked_by": blocked_by,
                "input_length": len(text)
            }
            
        except Exception as e:
            logger.error(f"Error during validation: {e}")
            return {
                "is_safe": False,
                "response": "Validation error occurred",
                "violations": [str(e)],
                "blocked_by": [],
                "input_length": len(text)
            }
    
    def _run_validator(self, validator: Dict[str, Any], text: str) -> tuple[bool, str]:
        """Run a specific validator against the input text"""
        validator_type = validator.get('type', '')
        
        if validator_type == 'regex':
            return self._run_regex_validator(validator, text)
        else:
            logger.warning(f"Unknown validator type: {validator_type}")
            return True, ""
    
    def _run_regex_validator(self, validator: Dict[str, Any], text: str) -> tuple[bool, str]:
        """Run regex pattern validation"""
        parameters = validator.get('parameters', {})
        patterns = parameters.get('patterns', [])
        ignore_case = parameters.get('ignore_case', False)
        
        flags = re.IGNORECASE if ignore_case else 0
        
        for pattern in patterns:
            if re.search(pattern, text, flags):
                fail_message = validator.get('on_fail', {}).get('message', 
                                           f"Content blocked by {validator['name']}")
                return False, fail_message
        
        return True, ""
    
    def _get_failure_response(self, validator_name: str) -> str:
        """Get the appropriate failure response based on flows"""
        # Check flows for handling this validator failure
        for flow_name, flow_config in self.flows.items():
            steps = flow_config.get('steps', [])
            for step in steps:
                condition = step.get('condition', '')
                
                # Simple condition parsing - you can extend this
                if validator_name and f"validate('{validator_name}')" in condition:
                    then_actions = step.get('then', [])
                    for action in then_actions:
                        if 'say' in action:
                            message = action['say']
                            # Handle template substitution
                            if 'fail_message(' in message:
                                # Extract validator name and get fail message
                                if validator_name in self.validators:
                                    return self.validators[validator_name].get('on_fail', {}).get('message', 
                                                                                               'Content not allowed')
                            return message
        
        # Default failure message
        return "I'm sorry, but that message isn't allowed."

# Global guardrails engine instance
guardrails_engine = None

def initialize_guardrails():
    """Initialize the custom guardrails engine"""
    global guardrails_engine
    try:
        config_path = "./rails"
        if not os.path.exists(config_path):
            logger.error(f"Rails config directory not found: {config_path}")
            return False
            
        guardrails_engine = GuardrailsEngine(config_path)
        logger.info("Custom guardrails engine initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize guardrails engine: {e}")
        return False

@app.on_event("startup")
async def startup_event():
    """Initialize guardrails on application startup"""
    success = initialize_guardrails()
    if not success:
        logger.warning("Guardrails initialization failed, continuing without guardrails")

@app.post("/validate_input", response_model=ValidationResponse)
async def validate_input(request: InputRequest):
    """
    Validate input text using custom YAML-based guardrails
    
    Args:
        request: InputRequest containing the text to validate
        
    Returns:
        ValidationResponse with validation results
    """
    if guardrails_engine is None:
        logger.warning("Guardrails not initialized, rejecting request")
        return ValidationResponse(
            is_safe=False,
            error="Guardrails system not available"
        )
    
    try:
        result = guardrails_engine.validate_input(request.text)
        
        return ValidationResponse(
            is_safe=result["is_safe"],
            response=result["response"],
            metadata={
                "violations": result.get("violations", []),
                "blocked_by": result.get("blocked_by", []),
                "input_length": result.get("input_length", 0)
            }
        )
        
    except Exception as e:
        logger.error(f"Error during validation: {e}")
        return ValidationResponse(
            is_safe=False,
            error=f"Validation error: {str(e)}"
        )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "guardrails_initialized": guardrails_engine is not None,
        "service": "custom-guardrails-validation"
    }

@app.get("/config")
async def get_config():
    """Get current guardrails configuration info"""
    if guardrails_engine is None:
        raise HTTPException(status_code=503, detail="Guardrails not initialized")
    
    try:
        config_info = {
            "config_path": "./rails",
            "validators": list(guardrails_engine.validators.keys()),
            "flows": list(guardrails_engine.flows.keys()),
            "rails_config": guardrails_engine.rails_config,
            "guardrails_available": True
        }
        return config_info
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Config error: {str(e)}")

@app.get("/validators")
async def get_validators():
    """Get detailed information about all configured validators"""
    if guardrails_engine is None:
        raise HTTPException(status_code=503, detail="Guardrails not initialized")
    
    return {
        "validators": guardrails_engine.validators,
        "count": len(guardrails_engine.validators)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        log_level="info"
    )
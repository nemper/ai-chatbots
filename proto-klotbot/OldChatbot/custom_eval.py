from re import search
from typing import Any, Optional
from langchain.chains import LLMChain
from langchain.chat_models import ChatOpenAI
from langchain.evaluation import StringEvaluator

class RelevanceEvaluator(StringEvaluator):
    def __init__(self):
        llm = ChatOpenAI(model="gpt-4", temperature=0)
        
        prompt = """On a scale from 1 to 5, how correct is the following response to the input:
        -------- INPUT: {input}
        -------- OUTPUT: {prediction}
        -------- Reason step by step about why the score is appropriate. At the end of your response, repeat that score alone on a new line."""
        self.eval_chain = LLMChain.from_string(llm=llm, template=prompt)

    @property
    def requires_input(self) -> bool:
        return True

    @property   # ostaje zbog interne logike StringEvaluator-a
    def requires_reference(self) -> bool:
        return False

    @property
    def evaluation_name(self) -> str:
        return "scored_relevance"

    def _evaluate_strings(
        self,
        prediction: str,
        input: Optional[str] = None,
        **kwargs: Any
    ) -> dict:
        evaluator_result = self.eval_chain(
            dict(input=input, prediction=prediction),
            **kwargs
        )
        reasoning, score = evaluator_result["text"].split("\n", maxsplit=1)
        score = search(r"\d+", score).group(0)
        score = float(score.strip()) if score is not None else 42
        return {"score": score, "reasoning": reasoning.strip()}

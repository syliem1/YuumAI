import { motion } from "motion/react";

const Response = ({questionType, choices}) => {
    const selectAll = (questionType==="selectAll")
    const multipleChoice = (questionType==="multipleChoice")
    const shortAnswer = (questionType==="shortAnswer")
        return(
            <motion.div initial={{x:100, opacity:0}} animate={{x:0, opacity:1}} transition={{delay: 2.5}} className="bg-background/90 w-1/4 flex flex-col items-center border-2 border-dark p-10 rounded-2xl text-2xl">
                {multipleChoice && (
                    <div>
                        <p> Choose One
                    </p>
                    {choices.map((item, index) => (
                        <div className="flex items-center justify-start gap-2">
                        <input key={index} type="radio" className="size-5"/> <p className="text-start">{item}</p>
                        </div>
                    ))}
                    </div>
                    
                    
                )}
                {selectAll && (
                    <p>select all that apply</p>
                )}
                {shortAnswer && (
                    <p>type your answer</p>
                )
                }
                {!multipleChoice && !selectAll && !shortAnswer && (
                    <p>invalid question type</p>
                )}
            
        </motion.div>
        )
    
}

export default Response;
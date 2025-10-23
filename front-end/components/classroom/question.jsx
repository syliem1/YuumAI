import { motion } from "motion/react";

const Question = ({text}) => {
    return(
        <motion.div initial={{y: 100, opacity: 0}} animate={{y: 0, opacity: 1}} transition={{delay: 2.5}} className="bg-background/90 w-10/12 border-2 border-dark p-10 rounded-2xl text-2xl">
            {text}
        </motion.div>
    )
}

export default Question;
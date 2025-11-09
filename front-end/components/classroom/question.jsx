import { motion } from "motion/react";

const Question = ({ text }) => {
  return (
    <motion.div
      initial={{ y: 100, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ delay: 2.5 }}
      className="w-10/12 rounded-2xl border-2 border-dark bg-background/90 p-10 text-2xl"
    >
      {text}
    </motion.div>
  );
};

export default Question;

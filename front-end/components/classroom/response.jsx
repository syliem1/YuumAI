import { motion } from "motion/react";

const Response = ({ questionType, choices, question }) => {
  const selectAll = questionType === "selectAll";
  const multipleChoice = questionType === "multipleChoice";
  const shortAnswer = questionType === "shortAnswer";
  return (
    <motion.div
      initial={{ x: 100, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      transition={{ delay: 2.5 }}
      className="flex w-1/4 flex-col items-center justify-center rounded-2xl border-2 border-dark bg-background/90 p-5 text-2xl"
    >
      <form>
        {multipleChoice && (
          <div>
            <p> Choose One</p>

            {choices.map((item, index) => (
              <div
                key={index}
                className="flex items-center justify-start gap-2"
              >
                <input type="radio" id={item} value={item} name={question} />{" "}
                <label for={item} className="text-start">
                  {item}
                </label>
              </div>
            ))}
            <input
              type="submit"
              className="cursor-pointer"
              value="next question"
            />
          </div>
        )}
        {selectAll && (
          <div>
            <p> Select all that apply</p>

            {choices.map((item, index) => (
              <div
                key={index}
                className="flex items-center justify-start gap-2"
              >
                <input type="checkbox" id={item} value={item} name={question} />{" "}
                <label for={item} className="text-start">
                  {item}
                </label>
              </div>
            ))}
            <input
              type="submit"
              className="cursor-pointer"
              value="next question"
            />
          </div>
        )}
        {shortAnswer && (
          <div>
            <p> type your answer</p>

            <div className="flex flex-col items-center justify-center gap-2 py-2">
              <input
                type="text"
                id={choices[0]}
                name={question}
                placeholder={choices[0]}
              />
            </div>
            <input
              type="submit"
              className="cursor-pointer"
              value="next question"
            />
          </div>
        )}
        {!multipleChoice && !selectAll && !shortAnswer && (
          <p>invalid question type</p>
        )}
      </form>
    </motion.div>
  );
};

export default Response;

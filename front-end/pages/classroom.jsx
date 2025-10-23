import classroombackground from "@/public/images/classroom-background.png";
import Image from "next/image";
import Question from "@/components/classroom/question";
import yuumiPlaceholder from "@/public/images/Yuumi_BattlePrincipalSkin.webp";
import Response from "@/components/classroom/response";
import { motion } from "motion/react";

const Classroom = () => {
  return (
    <div className="relative h-screen w-screen overflow-hidden bg-accent">
      <Image src={classroombackground} className="animate-blur-delay w-full" />
      <motion.div
        initial={{ x: -100, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        tansition={{ delay: 2.5 }}
        className="absolute inset-y-1/3 left-10 z-10 w-1/5"
      >
        <Image src={yuumiPlaceholder} className="object-contain" />
      </motion.div>

      <div className="absolute bottom-10 z-10 flex w-full flex-col items-center">
        <Question text={"question question question question question?"} />
      </div>
      <div className="absolute inset-y-1/3 right-20 z-10 flex w-full justify-end">
        <Response
          questionType={"shortAnswer"}
          choices={[
            "amazing answer choice",
            "baller answer choice",
            "really dumb and stupid answer choice",
          ]}
          question={"question question question question question?"}
        />
      </div>
    </div>
  );
};

export default Classroom;

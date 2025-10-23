import classroombackground from "@/public/images/classroom-background.png";
import Image from "next/image";
import Question from "@/components/classroom/question";
import yuumiPlaceholder from "@/public/images/Yuumi_BattlePrincipalSkin.webp";
import Response from "@/components/classroom/response";

const Classroom = () => {
    return(
        <div className="relative w-screen h-screen overflow-hidden bg-accent">
            <Image src={classroombackground} className="w-full animate-blur-delay"/>
            <Image src={yuumiPlaceholder} className="absolute inset-y-1/3 left-10 z-10 object-contain w-1/5"/>
            <div className="z-10 w-full absolute flex flex-col items-center bottom-10">
                <Question text={"question question question question question?"}/>
            </div>
            <div className="z-10 absolute right-20 inset-y-1/3 w-full flex justify-end">
                <Response questionType={"multipleChoice"} choices={["amazing answer choice", "baller answer choice", "really dumb and stupid answer choice"]}/>
            </div>
            
        </div>
    )
}

export default Classroom;
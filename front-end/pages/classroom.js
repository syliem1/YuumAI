import classroombackground from "@/public/images/classroom-background.png";
import Image from "next/image";

const Classroom = () => {
    return(
        <div className="flex flex-col items-center w-full h-full overflow-hidden bg-black">
            <Image src={classroombackground} className="w-full animate-blur-delay "/>
        </div>
    )
}

export default Classroom;
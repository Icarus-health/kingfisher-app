import type {CloudMemoryPreview, CloudMemoryPurpose} from "./api";

/** Stay on a page until its unprocessed sources are exhausted. No inference here. */
export async function prepareCloudPreview(
  request:(purpose:CloudMemoryPurpose,cursor?:number)=>Promise<CloudMemoryPreview>,
  purpose:CloudMemoryPurpose,cursor?:number,
) {
  let page:CloudMemoryPreview;
  for(let attempt=0;attempt<4;attempt++) {
    page=await request(purpose,cursor);
    if(page.count>0||page.next_cursor===null||purpose!=="bulk"||attempt===3) {
      return {preview:page,cursor};
    }
    cursor=page.next_cursor;
  }
  throw new Error("Vorschau konnte nicht erstellt werden.");
}
